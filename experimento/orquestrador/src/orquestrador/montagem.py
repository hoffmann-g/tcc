"""Montagem do histórico de posse a partir dos eventos dos coletores e do traço executado.

Aplica as regras de fechamento da seção 6 da formalização:

1. início de posse no evento `atribuida`;
2. fim de posse no evento `revogada` ou `perdida`, com o tipo correspondente;
3. trabalhador morto pelo orquestrador: intervalos abertos fechados no instante do
   `SIGKILL`, com tipo `externo`;
4. intervalos ainda abertos em T1: fechados em T1 com tipo `janela`;
5. a época do intervalo é a do evento `atribuida`.

Também compara a base de tempo entre o orquestrador e cada coletor.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from verificador.historico import Fechamento, Intervalo, escrever_csv
from verificador.relatorio import Relatorio, relatorio

COLUNAS_EVENTOS = ("evento", "trabalhador", "particao", "epoca", "mono_ns", "relogio_ns")
COLUNAS_ACOES = ("t_planejado_s", "acao", "trabalhador", "mono_ns", "relogio_ns", "pid", "detalhe")

EVENTOS_DE_PROCESSO = frozenset({"processo_inicio", "processo_fim"})


@dataclass(frozen=True, slots=True)
class EventoColetor:
    evento: str
    trabalhador: str
    particao: str
    epoca: int
    mono_ns: int
    relogio_ns: int


@dataclass(frozen=True, slots=True)
class AcaoExecutada:
    t_planejado_s: float
    acao: str
    trabalhador: str
    mono_ns: int
    relogio_ns: int
    pid: int | None
    detalhe: str


@dataclass(frozen=True, slots=True)
class BaseTempo:
    """Desvio entre o relógio monotônico lido pelo coletor e pelo orquestrador.

    Usa dois instantes, um em cada processo, e a diferença dos relógios de parede entre
    eles como referência: desvio = (mono_coletor - mono_orq) - (relogio_coletor -
    relogio_orq). Se ambos leem CLOCK_MONOTONIC, o desvio fica na resolução do relógio de
    parede.
    """

    trabalhador: str
    desvio_ns: int


@dataclass(slots=True)
class Montagem:
    intervalos: list[Intervalo]
    anomalias: list[str]
    base_tempo: list[BaseTempo]

    @property
    def erro_base_tempo_ns(self) -> int:
        return max((abs(b.desvio_ns) for b in self.base_tempo), default=0)


def ler_eventos(caminhos: Iterable[str | Path]) -> list[EventoColetor]:
    eventos: list[EventoColetor] = []
    for caminho in caminhos:
        with open(caminho, newline="", encoding="utf-8") as arquivo:
            for linha in csv.DictReader(arquivo):
                eventos.append(
                    EventoColetor(
                        evento=linha["evento"],
                        trabalhador=linha["trabalhador"],
                        particao=linha["particao"],
                        epoca=int(linha["epoca"]),
                        mono_ns=int(linha["mono_ns"]),
                        relogio_ns=int(linha["relogio_ns"]),
                    )
                )
    return eventos


def ler_acoes(caminho: str | Path) -> list[AcaoExecutada]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return [
            AcaoExecutada(
                t_planejado_s=float(l["t_planejado_s"]),
                acao=l["acao"],
                trabalhador=l["trabalhador"],
                mono_ns=int(l["mono_ns"]),
                relogio_ns=int(l["relogio_ns"]),
                pid=int(l["pid"]) if l["pid"] else None,
                detalhe=l["detalhe"],
            )
            for l in csv.DictReader(arquivo)
        ]


def montar(eventos: Iterable[EventoColetor], acoes: Iterable[AcaoExecutada], t0: int, t1: int) -> Montagem:
    acoes = list(acoes)
    mortes = {a.trabalhador: a.mono_ns for a in acoes if a.acao == "matar"}
    abertos: dict[tuple[str, str], tuple[int, int]] = {}
    intervalos: list[Intervalo] = []
    anomalias: list[str] = []

    for e in sorted(eventos, key=lambda e: e.mono_ns):
        if e.evento in EVENTOS_DE_PROCESSO:
            continue
        if not e.particao:
            anomalias.append(f"evento {e.evento} de {e.trabalhador} em {e.mono_ns} sem partição; ignorado")
            continue
        if e.mono_ns >= t1:
            continue
        if e.mono_ns < t0:
            anomalias.append(f"evento {e.evento} de {e.trabalhador} em {e.mono_ns}, antes de T0")
            continue
        morte = mortes.get(e.trabalhador)
        if morte is not None and e.mono_ns >= morte:
            anomalias.append(
                f"evento {e.evento} de {e.trabalhador} sobre {e.particao} em {e.mono_ns}, depois da morte em {morte}"
            )
            continue
        chave = (e.trabalhador, e.particao)
        if e.evento == "atribuida":
            if chave in abertos:
                epoca, inicio = abertos[chave]
                anomalias.append(
                    f"atribuição dupla de {e.particao} a {e.trabalhador} em {e.mono_ns}; "
                    f"intervalo aberto em {inicio} fechado como revogada"
                )
                intervalos.append(Intervalo(e.trabalhador, e.particao, epoca, inicio, e.mono_ns, Fechamento.REVOGADA))
            abertos[chave] = (e.epoca, e.mono_ns)
        elif e.evento in ("revogada", "perdida"):
            if chave not in abertos:
                anomalias.append(f"{e.evento} de {e.particao} em {e.trabalhador} em {e.mono_ns} sem atribuição aberta")
                continue
            epoca, inicio = abertos.pop(chave)
            intervalos.append(Intervalo(e.trabalhador, e.particao, epoca, inicio, e.mono_ns, Fechamento(e.evento)))
        else:
            anomalias.append(f"evento desconhecido {e.evento} de {e.trabalhador}")

    for (trabalhador, particao), (epoca, inicio) in abertos.items():
        morte = mortes.get(trabalhador)
        if morte is not None and morte < t1:
            intervalos.append(Intervalo(trabalhador, particao, epoca, inicio, morte, Fechamento.EXTERNO))
        else:
            intervalos.append(Intervalo(trabalhador, particao, epoca, inicio, t1, Fechamento.JANELA))

    intervalos.sort(key=lambda i: (i.particao, i.inicio, i.trabalhador))
    return Montagem(intervalos, anomalias, base_tempo(eventos, acoes))


def base_tempo(eventos: Iterable[EventoColetor], acoes: Iterable[AcaoExecutada]) -> list[BaseTempo]:
    entradas = {a.trabalhador: a for a in acoes if a.acao == "entrar"}
    desvios: list[BaseTempo] = []
    for e in eventos:
        if e.evento != "processo_inicio" or e.trabalhador not in entradas:
            continue
        a = entradas[e.trabalhador]
        desvio = (e.mono_ns - a.mono_ns) - (e.relogio_ns - a.relogio_ns)
        desvios.append(BaseTempo(e.trabalhador, desvio))
    return desvios


def montar_execucao(pasta: str | Path) -> tuple[Montagem, Relatorio]:
    """Monta o histórico de uma execução gravada em disco e roda o verificador.

    Lê `execucao.json`, `traco-executado.csv` e `eventos-*.csv`; escreve `historico.csv`,
    `montagem.json`, `relatorio.txt` e `relatorio.json`. A margem do verificador é o erro
    medido da base de tempo.
    """
    pasta = Path(pasta)
    info = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
    eventos = ler_eventos(sorted(pasta.glob("eventos-*.csv")))
    acoes = ler_acoes(pasta / "traco-executado.csv")
    t0, t1 = int(info["t0_mono_ns"]), int(info["t1_mono_ns"])

    m = montar(eventos, acoes, t0, t1)
    escrever_csv(pasta / "historico.csv", m.intervalos)
    particoes = [f"{info['topico']}-{i}" for i in range(int(info["particoes"]))]
    rel = relatorio(m.intervalos, janela=(t0, t1), margem=m.erro_base_tempo_ns, particoes=particoes)

    (pasta / "relatorio.txt").write_text(rel.texto() + "\n", encoding="utf-8")
    (pasta / "relatorio.json").write_text(json.dumps(rel.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "montagem.json").write_text(
        json.dumps(
            {
                "intervalos": len(m.intervalos),
                "anomalias": m.anomalias,
                "base_tempo": [asdict(b) for b in m.base_tempo],
                "erro_base_tempo_ns": m.erro_base_tempo_ns,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return m, rel
