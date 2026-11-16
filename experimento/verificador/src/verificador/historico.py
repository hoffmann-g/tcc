"""Leitura, validação e escrita do histórico de posse.

O histórico é o conjunto de intervalos de posse da seção 3 da formalização. Cada linha
afirma que um trabalhador se considerou responsável por uma partição, sob uma época,
durante [inicio, fim). Os instantes são inteiros em nanossegundos de um relógio
monotônico comum a todos os processos. O campo fechamento diz como o fim foi observado
(regras de fechamento, seção 6).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class HistoricoInvalido(ValueError):
    """O arquivo não é um histórico válido."""


class Fechamento(StrEnum):
    REVOGADA = "revogada"  # onPartitionsRevoked
    PERDIDA = "perdida"  # onPartitionsLost
    EXTERNO = "externo"  # instante do sinal enviado pelo orquestrador
    JANELA = "janela"  # ainda aberto no fim da janela; fechado em T1


COLUNAS = ("trabalhador", "particao", "epoca", "inicio", "fim", "fechamento")


@dataclass(frozen=True, slots=True)
class Intervalo:
    trabalhador: str
    particao: str
    epoca: int
    inicio: int
    fim: int
    fechamento: Fechamento

    def __post_init__(self) -> None:
        if self.fim < self.inicio:
            raise HistoricoInvalido(f"fim anterior ao início: {self}")

    @property
    def duracao(self) -> int:
        return self.fim - self.inicio

    def linha(self) -> dict[str, str]:
        return {
            "trabalhador": self.trabalhador,
            "particao": self.particao,
            "epoca": str(self.epoca),
            "inicio": str(self.inicio),
            "fim": str(self.fim),
            "fechamento": self.fechamento.value,
        }


def ler_csv(caminho: str | Path) -> list[Intervalo]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        cabecalho = tuple(c.strip() for c in leitor.fieldnames or ())
        faltando = [c for c in COLUNAS if c not in cabecalho]
        if faltando:
            raise HistoricoInvalido(f"colunas ausentes no cabeçalho: {', '.join(faltando)}")
        return [_intervalo(linha, numero) for numero, linha in enumerate(leitor, start=2)]


def _intervalo(linha: dict[str, str], numero: int) -> Intervalo:
    try:
        campos = {c: (linha[c] or "").strip() for c in COLUNAS}
        return Intervalo(
            trabalhador=campos["trabalhador"],
            particao=campos["particao"],
            epoca=int(campos["epoca"]),
            inicio=int(campos["inicio"]),
            fim=int(campos["fim"]),
            fechamento=Fechamento(campos["fechamento"]),
        )
    except (KeyError, ValueError) as erro:
        raise HistoricoInvalido(f"linha {numero}: {erro}") from erro


def escrever_csv(caminho: str | Path, intervalos: Iterable[Intervalo]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        for intervalo in intervalos:
            escritor.writerow(intervalo.linha())


def por_particao(intervalos: Iterable[Intervalo]) -> dict[str, list[Intervalo]]:
    grupos: dict[str, list[Intervalo]] = defaultdict(list)
    for intervalo in intervalos:
        grupos[intervalo.particao].append(intervalo)
    return dict(grupos)


def trabalhadores(intervalos: Iterable[Intervalo]) -> set[str]:
    return {i.trabalhador for i in intervalos}


def janela_padrao(intervalos: list[Intervalo]) -> tuple[int, int]:
    """[menor início, maior fim) do histórico."""
    if not intervalos:
        raise HistoricoInvalido("histórico vazio: a janela precisa ser informada")
    return min(i.inicio for i in intervalos), max(i.fim for i in intervalos)
