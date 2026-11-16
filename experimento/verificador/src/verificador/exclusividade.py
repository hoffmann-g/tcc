"""Exclusividade de posse (seção 4.1 da formalização).

Um histórico satisfaz exclusividade quando, para quaisquer dois intervalos da mesma
partição com trabalhadores distintos, os intervalos [s1, f1) e [s2, f2) são disjuntos.
A violação é uma sobreposição, com duração min(f1, f2) - max(s1, s2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from verificador.historico import Fechamento, Intervalo, por_particao


@dataclass(frozen=True, slots=True)
class Sobreposicao:
    particao: str
    a: Intervalo
    b: Intervalo
    inicio: int
    fim: int

    @property
    def duracao(self) -> int:
        return self.fim - self.inicio


def sobreposicoes(intervalos: Iterable[Intervalo], margem: int = 0) -> list[Sobreposicao]:
    """Sobreposições com duração maior que a margem, ordenadas por partição e início.

    Intervalos com fechamento `janela` não entram: o fim não foi observado, e a regra 4
    da seção 6 os reporta separadamente. Dois intervalos do mesmo trabalhador nunca
    constituem violação, qualquer que seja a época.

    Varredura por partição: os intervalos são ordenados por início, e um conjunto de
    ativos guarda os que ainda podem cruzar os próximos. Como max(s1, s2) é sempre o
    início do intervalo corrente, um ativo cuja distância até esse início é menor ou
    igual à margem não cruza nem o corrente nem nenhum posterior, e sai do conjunto.
    """
    if margem < 0:
        raise ValueError("margem negativa")
    resultado: list[Sobreposicao] = []
    for particao, grupo in por_particao(intervalos).items():
        candidatos = sorted(
            (i for i in grupo if i.fechamento is not Fechamento.JANELA),
            key=lambda i: (i.inicio, i.fim),
        )
        ativos: list[Intervalo] = []
        for atual in candidatos:
            ativos = [a for a in ativos if a.fim - atual.inicio > margem]
            for ativo in ativos:
                if ativo.trabalhador == atual.trabalhador:
                    continue
                fim = min(ativo.fim, atual.fim)
                if fim - atual.inicio > margem:
                    resultado.append(Sobreposicao(particao, ativo, atual, atual.inicio, fim))
            ativos.append(atual)
    resultado.sort(key=lambda s: (s.particao, s.inicio, s.fim))
    return resultado
