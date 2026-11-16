"""Traço de churn: sequência temporizada de entrada, saída, morte e suspensão de
trabalhadores, descrita em termos independentes do sistema sob observação.

Arquivo TOML:

    nome = "piloto"
    particoes = 8
    duracao_s = 90

    [[eventos]]
    t = 0
    acao = "entrar"
    trabalhador = "w1"

    [[eventos]]
    t = 30
    acao = "suspender"
    trabalhador = "w1"
    duracao = 20

Ações: `entrar` inicia um trabalhador; `sair` o encerra de forma ordenada (SIGTERM, que
passa por `close()` e dispara `onPartitionsRevoked`); `matar` o encerra sem aviso
(SIGKILL, nenhum callback; o orquestrador fecha os intervalos como externo); `suspender`
congela o processo por `duracao` segundos (SIGSTOP e SIGCONT). Uma suspensão maior que o
tempo de sessão é a condição sob a qual a violação de exclusividade pode ocorrer.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class TracoInvalido(ValueError):
    pass


class Acao(StrEnum):
    ENTRAR = "entrar"
    SAIR = "sair"
    MATAR = "matar"
    SUSPENDER = "suspender"


@dataclass(frozen=True, slots=True)
class Evento:
    t: float
    acao: Acao
    trabalhador: str
    duracao: float | None = None


@dataclass(frozen=True, slots=True)
class Traco:
    nome: str
    particoes: int
    duracao_s: float
    eventos: tuple[Evento, ...]
    descricao: str = ""

    @property
    def trabalhadores(self) -> list[str]:
        vistos: dict[str, None] = {}
        for e in self.eventos:
            vistos.setdefault(e.trabalhador)
        return list(vistos)


def carregar(caminho: str | Path) -> Traco:
    with open(caminho, "rb") as arquivo:
        return construir(tomllib.load(arquivo))


def construir(dados: dict[str, Any]) -> Traco:
    try:
        nome = str(dados["nome"])
        particoes = int(dados["particoes"])
        duracao_s = float(dados["duracao_s"])
    except KeyError as erro:
        raise TracoInvalido(f"campo obrigatório ausente: {erro}") from erro
    except (TypeError, ValueError) as erro:
        raise TracoInvalido(str(erro)) from erro
    brutos = dados.get("eventos", [])
    eventos = tuple(sorted((_evento(e, i) for i, e in enumerate(brutos, start=1)), key=lambda e: e.t))
    traco = Traco(nome, particoes, duracao_s, eventos, str(dados.get("descricao", "")))
    validar(traco)
    return traco


def _evento(d: dict[str, Any], indice: int) -> Evento:
    try:
        acao = Acao(d["acao"])
        t = float(d["t"])
        trabalhador = str(d["trabalhador"])
    except (KeyError, TypeError, ValueError) as erro:
        raise TracoInvalido(f"evento {indice}: {erro}") from erro
    duracao = d.get("duracao")
    if acao is Acao.SUSPENDER and duracao is None:
        raise TracoInvalido(f"evento {indice}: suspender exige duracao")
    if acao is not Acao.SUSPENDER and duracao is not None:
        raise TracoInvalido(f"evento {indice}: duracao só se aplica a suspender")
    return Evento(t, acao, trabalhador, None if duracao is None else float(duracao))


def validar(traco: Traco) -> None:
    """Simula o traço e rejeita sequências impossíveis.

    Um nome de trabalhador é usado uma única vez: o orquestrador indexa a morte pelo nome.
    `sair` exige processo em execução; `SIGTERM` em processo parado só é tratado na
    retomada. `matar` é permitido durante a suspensão: `SIGKILL` age sobre processo parado.
    """
    if traco.particoes < 1:
        raise TracoInvalido("particoes precisa ser ao menos 1")
    if traco.duracao_s <= 0:
        raise TracoInvalido("duracao_s precisa ser positiva")
    if not traco.eventos:
        raise TracoInvalido("traço sem eventos")
    vivos: set[str] = set()
    ja_usados: set[str] = set()
    suspensos: dict[str, float] = {}
    for e in traco.eventos:
        if not 0 <= e.t < traco.duracao_s:
            raise TracoInvalido(f"t={e.t} fora de [0, {traco.duracao_s})")
        for w, retomada in list(suspensos.items()):
            if retomada <= e.t:
                del suspensos[w]
        w = e.trabalhador
        match e.acao:
            case Acao.ENTRAR:
                if w in ja_usados:
                    raise TracoInvalido(f"{w} entra mais de uma vez; use outro nome")
                vivos.add(w)
                ja_usados.add(w)
            case Acao.SAIR:
                if w not in vivos:
                    raise TracoInvalido(f"{w} sai em t={e.t} sem estar em execução")
                if w in suspensos:
                    raise TracoInvalido(f"{w} sai em t={e.t} enquanto suspenso")
                vivos.remove(w)
            case Acao.MATAR:
                if w not in vivos:
                    raise TracoInvalido(f"{w} é morto em t={e.t} sem estar em execução")
                vivos.remove(w)
                suspensos.pop(w, None)
            case Acao.SUSPENDER:
                if w not in vivos:
                    raise TracoInvalido(f"{w} é suspenso em t={e.t} sem estar em execução")
                if w in suspensos:
                    raise TracoInvalido(f"{w} é suspenso em t={e.t} já estando suspenso")
                assert e.duracao is not None
                if e.duracao <= 0:
                    raise TracoInvalido(f"suspensão de {w} com duração não positiva")
                if e.t + e.duracao > traco.duracao_s:
                    raise TracoInvalido(f"retomada de {w} em t={e.t + e.duracao} depois do fim")
                suspensos[w] = e.t + e.duracao
