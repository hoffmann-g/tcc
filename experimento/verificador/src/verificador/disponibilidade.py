"""Disponibilidade e tempo órfão (seção 4.2 da formalização).

Uma partição está coberta em t quando existe no histórico um intervalo de posse que
contém t; caso contrário está órfã. O tempo órfão de uma partição em [T0, T1) é a medida
do conjunto de instantes em que ela está órfã. É definido sobre a partição, não sobre o
grupo, e por isso é comparável entre protocolos.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from verificador.historico import Intervalo, por_particao


@dataclass(frozen=True, slots=True)
class Lacuna:
    inicio: int
    fim: int

    @property
    def duracao(self) -> int:
        return self.fim - self.inicio


@dataclass(frozen=True, slots=True)
class Cobertura:
    particao: str
    janela: tuple[int, int]
    lacunas: tuple[Lacuna, ...]

    @property
    def tempo_orfao(self) -> int:
        return sum(l.duracao for l in self.lacunas)

    @property
    def fracao_orfa(self) -> float:
        largura = self.janela[1] - self.janela[0]
        return self.tempo_orfao / largura if largura else 0.0

    @property
    def coberta_no_fim(self) -> bool:
        """Verdadeiro se a partição está coberta no último instante da janela."""
        return not self.lacunas or self.lacunas[-1].fim < self.janela[1]


def cobertura(
    intervalos: Iterable[Intervalo],
    janela: tuple[int, int],
    particoes: Sequence[str] | None = None,
) -> dict[str, Cobertura]:
    """Lacunas de cobertura por partição dentro da janela.

    Todos os fechamentos contam como cobertura, inclusive `janela`: um intervalo aberto no
    fim da observação cobriu a partição até T1. Partições listadas em `particoes` e
    ausentes do histórico ficam órfãs na janela inteira.
    """
    inicio_janela, fim_janela = janela
    if fim_janela < inicio_janela:
        raise ValueError("janela com fim anterior ao início")
    grupos = por_particao(intervalos)
    nomes = list(particoes) if particoes is not None else sorted(grupos)
    resultado: dict[str, Cobertura] = {}
    for particao in nomes:
        recortados = sorted(
            (max(i.inicio, inicio_janela), min(i.fim, fim_janela))
            for i in grupos.get(particao, ())
            if i.fim > inicio_janela and i.inicio < fim_janela
        )
        lacunas: list[Lacuna] = []
        cursor = inicio_janela
        for inicio, fim in recortados:
            if inicio > cursor:
                lacunas.append(Lacuna(cursor, inicio))
            cursor = max(cursor, fim)
        if cursor < fim_janela:
            lacunas.append(Lacuna(cursor, fim_janela))
        resultado[particao] = Cobertura(particao, janela, tuple(lacunas))
    return resultado


@dataclass(frozen=True, slots=True)
class Distribuicao:
    quantidade: int
    total: int
    minimo: int | None
    mediana: int | None
    p90: int | None
    maximo: int | None


def distribuicao(duracoes: Iterable[int]) -> Distribuicao:
    valores = sorted(duracoes)
    if not valores:
        return Distribuicao(0, 0, None, None, None, None)

    def percentil(q: float) -> int:
        posicao = max(math.ceil(q * len(valores)) - 1, 0)
        return valores[posicao]

    return Distribuicao(
        quantidade=len(valores),
        total=sum(valores),
        minimo=valores[0],
        mediana=percentil(0.5),
        p90=percentil(0.9),
        maximo=valores[-1],
    )
