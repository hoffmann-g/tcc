"""Execução de um traço contra um agrupamento Kafka real.

O orquestrador é o adaptador da proposta: a única peça que liga o traço, independente do
sistema, ao sistema sob observação. Cria um tópico novo por execução, lança os coletores
como processos JVM no host, aplica os sinais do traço nos instantes previstos e registra
o instante real de cada ação em `traco-executado.csv`. Ao fim, monta o histórico e roda o
verificador.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from orquestrador import montagem
from orquestrador.traco import Acao, Traco

PROTOCOLOS = ("eager", "cooperativo", "kip848")


class ErroExecucao(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Parametros:
    protocolo: str
    coletor: Path
    saida: Path
    bootstrap: str = "localhost:9092"
    container: str = "tcc-kafka"
    sessao_ms: int = 10_000
    heartbeat_ms: int = 3_000
    poll_ms: int = 500
    trabalho_ms: int = 0


@dataclass(frozen=True, slots=True)
class Passo:
    t: float
    acao: str  # entrar | sair | matar | suspender | retomar
    trabalhador: str


class RegistroAcoes:
    def __init__(self, caminho: Path) -> None:
        self._arquivo = open(caminho, "w", newline="", encoding="utf-8")
        self._escritor = csv.writer(self._arquivo)
        self._escritor.writerow(montagem.COLUNAS_ACOES)

    def registrar(
        self,
        t_planejado: float,
        acao: str,
        trabalhador: str = "",
        pid: int | None = None,
        detalhe: str = "",
        instante: tuple[int, int] | None = None,
    ) -> int:
        mono, relogio = instante or agora()
        self._escritor.writerow(
            [f"{t_planejado:.3f}", acao, trabalhador, mono, relogio, "" if pid is None else pid, detalhe]
        )
        self._arquivo.flush()
        return mono

    def close(self) -> None:
        self._arquivo.close()


def agora() -> tuple[int, int]:
    """Par (monotônico, parede), com o monotônico no ponto médio de duas leituras que
    cercam a leitura do relógio de parede. Mesmo método do coletor."""
    antes = time.monotonic_ns()
    relogio = time.time_ns()
    depois = time.monotonic_ns()
    return antes + (depois - antes) // 2, relogio


def agenda(traco: Traco) -> list[Passo]:
    passos: list[Passo] = []
    for e in traco.eventos:
        passos.append(Passo(e.t, e.acao.value, e.trabalhador))
        if e.acao is Acao.SUSPENDER:
            assert e.duracao is not None
            passos.append(Passo(e.t + e.duracao, "retomar", e.trabalhador))
    passos.sort(key=lambda p: p.t)
    return passos


def comando_coletor(p: Parametros, trabalhador: str, grupo: str, topico: str, saida: Path, log: Path) -> list[str]:
    classpath = f"{p.coletor / 'out'}:{p.coletor / 'lib'}/*"
    return [
        "java",
        "-cp",
        classpath,
        f"-Dorg.slf4j.simpleLogger.logFile={log}",
        "-Dorg.slf4j.simpleLogger.defaultLogLevel=info",
        "-Dorg.slf4j.simpleLogger.showDateTime=true",
        "-Dorg.slf4j.simpleLogger.dateTimeFormat=HH:mm:ss.SSS",
        "Coletor",
        f"trabalhador={trabalhador}",
        f"protocolo={p.protocolo}",
        f"grupo={grupo}",
        f"topico={topico}",
        f"saida={saida}",
        f"bootstrap={p.bootstrap}",
        f"sessao_ms={p.sessao_ms}",
        f"heartbeat_ms={p.heartbeat_ms}",
        f"poll_ms={p.poll_ms}",
        f"trabalho_ms={p.trabalho_ms}",
    ]


def conferir_ambiente(p: Parametros) -> None:
    if p.protocolo not in PROTOCOLOS:
        raise ErroExecucao(f"protocolo desconhecido: {p.protocolo}; use {', '.join(PROTOCOLOS)}")
    if shutil.which("java") is None:
        raise ErroExecucao("java não encontrado no PATH")
    if not (p.coletor / "out" / "Coletor.class").exists():
        raise ErroExecucao(f"coletor não compilado em {p.coletor}; rode coletor/compilar.sh")
    if not list((p.coletor / "lib").glob("kafka-clients-*.jar")):
        raise ErroExecucao(f"dependências ausentes em {p.coletor / 'lib'}; rode coletor/deps.sh")
    if shutil.which("docker") is None:
        raise ErroExecucao("docker não encontrado no PATH")
    saude = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", p.container],
        capture_output=True,
        text=True,
    )
    if saude.returncode != 0 or saude.stdout.strip() != "healthy":
        estado = saude.stdout.strip() or saude.stderr.strip()
        raise ErroExecucao(
            f"broker {p.container} não está saudável ({estado}); suba com "
            "`docker compose -f ambiente/compose.yaml up -d` e aguarde"
        )


def criar_topico(container: str, topico: str, particoes: int) -> None:
    resultado = subprocess.run(
        [
            "docker", "exec", container, "/opt/kafka/bin/kafka-topics.sh",
            "--bootstrap-server", "localhost:9092",
            "--create", "--topic", topico,
            "--partitions", str(particoes), "--replication-factor", "1",
        ],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise ErroExecucao(f"falha ao criar o tópico {topico}: {resultado.stderr.strip() or resultado.stdout.strip()}")


def versao_java() -> str:
    saida = subprocess.run(["java", "-version"], capture_output=True, text=True)
    return (saida.stderr or saida.stdout).strip().splitlines()[0] if (saida.stderr or saida.stdout) else ""


def imagem_broker(container: str) -> str:
    saida = subprocess.run(["docker", "inspect", "-f", "{{.Config.Image}}", container], capture_output=True, text=True)
    return saida.stdout.strip()


def versao_cliente(coletor: Path) -> str:
    jars = sorted((coletor / "lib").glob("kafka-clients-*.jar"))
    return jars[0].stem.removeprefix("kafka-clients-") if jars else ""


def _informar(mensagem: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {mensagem}", file=sys.stderr, flush=True)


def executar(traco: Traco, p: Parametros) -> Path:
    conferir_ambiente(p)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    ident = f"{traco.nome}-{p.protocolo}-{carimbo}"
    pasta = p.saida / ident
    pasta.mkdir(parents=True)
    criar_topico(p.container, ident, traco.particoes)
    _informar(f"execução {ident}: tópico com {traco.particoes} partições criado")

    processos: dict[str, subprocess.Popen[bytes]] = {}
    saindo: dict[str, subprocess.Popen[bytes]] = {}
    logs: list = []
    registro = RegistroAcoes(pasta / "traco-executado.csv")
    t1: int | None = None
    t0 = registro.registrar(0.0, "inicio", detalhe=ident)
    t0_relogio = time.time_ns()

    def reaper(t_planejado: float) -> None:
        for w, proc in list(saindo.items()):
            codigo = proc.poll()
            if codigo is not None:
                registro.registrar(t_planejado, "saiu", w, proc.pid, detalhe=str(codigo))
                del saindo[w]

    def esperar(t_alvo: float) -> None:
        alvo = t0 + int(t_alvo * 1e9)
        while (resta := alvo - time.monotonic_ns()) > 0:
            reaper(t_alvo)
            time.sleep(min(resta / 1e9, 0.2))

    try:
        for passo in agenda(traco):
            esperar(passo.t)
            w = passo.trabalhador
            match passo.acao:
                case "entrar":
                    log = open(pasta / f"coletor-{w}.log", "ab")
                    logs.append(log)
                    cmd = comando_coletor(p, w, ident, ident, pasta / f"eventos-{w}.csv", pasta / f"cliente-{w}.log")
                    instante = agora()
                    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=pasta)
                    processos[w] = proc
                    registro.registrar(passo.t, "entrar", w, proc.pid, instante=instante)
                    _informar(f"t={passo.t:6.1f}  entrar    {w} (pid {proc.pid})")
                case "sair":
                    proc = processos.pop(w)
                    registro.registrar(passo.t, "sair", w, proc.pid)
                    proc.send_signal(signal.SIGTERM)
                    saindo[w] = proc
                    _informar(f"t={passo.t:6.1f}  sair      {w}")
                case "matar":
                    proc = processos.pop(w)
                    registro.registrar(passo.t, "matar", w, proc.pid)
                    proc.kill()
                    proc.wait(timeout=10)
                    _informar(f"t={passo.t:6.1f}  matar     {w}")
                case "suspender":
                    proc = processos[w]
                    registro.registrar(passo.t, "suspender", w, proc.pid)
                    os.kill(proc.pid, signal.SIGSTOP)
                    _informar(f"t={passo.t:6.1f}  suspender {w}")
                case "retomar":
                    proc = processos[w]
                    registro.registrar(passo.t, "retomar", w, proc.pid)
                    os.kill(proc.pid, signal.SIGCONT)
                    _informar(f"t={passo.t:6.1f}  retomar   {w}")
        esperar(traco.duracao_s)
        t1 = registro.registrar(traco.duracao_s, "fim")
        _informar(f"t={traco.duracao_s:6.1f}  fim da janela")
    finally:
        if t1 is None:
            t1 = registro.registrar(traco.duracao_s, "fim", detalhe="interrompido")
        for w, proc in list(processos.items()):
            if proc.poll() is None:
                registro.registrar(traco.duracao_s, "encerrar", w, proc.pid)
                try:
                    os.kill(proc.pid, signal.SIGCONT)
                except ProcessLookupError:
                    pass
                proc.send_signal(signal.SIGTERM)
            saindo[w] = proc
        limite = time.monotonic() + 30
        while saindo and time.monotonic() < limite:
            reaper(traco.duracao_s)
            time.sleep(0.1)
        for w, proc in saindo.items():
            proc.kill()
            registro.registrar(traco.duracao_s, "saiu", w, proc.pid, detalhe="forçado")
        registro.close()
        for log in logs:
            log.close()

    (pasta / "execucao.json").write_text(
        json.dumps(
            {
                "nome": traco.nome,
                "descricao": traco.descricao,
                "protocolo": p.protocolo,
                "topico": ident,
                "grupo": ident,
                "particoes": traco.particoes,
                "duracao_s": traco.duracao_s,
                "t0_mono_ns": t0,
                "t1_mono_ns": t1,
                "t0_relogio_ns": t0_relogio,
                "sessao_ms": p.sessao_ms,
                "heartbeat_ms": p.heartbeat_ms,
                "poll_ms": p.poll_ms,
                "trabalho_ms": p.trabalho_ms,
                "sessao_definida_em": "servidor" if p.protocolo == "kip848" else "cliente",
                "broker": imagem_broker(p.container),
                "kafka_clients": versao_cliente(p.coletor),
                "java": versao_java(),
                "trabalhadores": traco.trabalhadores,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    m, rel = montagem.montar_execucao(pasta)
    _informar(
        f"histórico com {len(m.intervalos)} intervalos, {len(m.anomalias)} anomalias, "
        f"erro da base de tempo {m.erro_base_tempo_ns} ns"
    )
    return pasta
