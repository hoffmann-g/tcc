"""Históricos sintéticos para validar o verificador (C5 do plano, validação no sentido 3).

Os geradores reproduzem os três padrões de rebalanceamento da seção 5.3 da formalização
como históricos ideais, sem o Kafka, e permitem plantar violações com duração conhecida.
"""

from __future__ import annotations

from collections.abc import Sequence

from verificador.historico import Fechamento, Intervalo


def atribuicao(particoes: Sequence[str], membros: Sequence[str]) -> dict[str, str]:
    """Atribuição circular: a k-ésima partição vai ao (k mod |M|)-ésimo membro."""
    if not membros:
        return {}
    return {p: membros[k % len(membros)] for k, p in enumerate(particoes)}


def eager(
    particoes: Sequence[str],
    visoes: Sequence[Sequence[str]],
    instantes: Sequence[int],
    fim: int,
    barreira: int,
) -> list[Intervalo]:
    """Padrão eager: toda posse termina no instante do rebalanceamento e a nova começa
    depois da barreira. Nenhuma partição está coberta durante a barreira."""
    _conferir(visoes, instantes, fim)
    historico: list[Intervalo] = []
    limites = [*instantes, fim]
    for epoca, (membros, inicio, proximo) in enumerate(zip(visoes, limites, limites[1:]), start=1):
        for particao, membro in atribuicao(particoes, membros).items():
            historico.append(
                Intervalo(membro, particao, epoca, inicio + barreira, proximo, Fechamento.REVOGADA)
            )
    return historico


def cooperativo(
    particoes: Sequence[str],
    visoes: Sequence[Sequence[str]],
    instantes: Sequence[int],
    fim: int,
    atraso: int,
) -> list[Intervalo]:
    """Padrão cooperativo: só as partições que trocam de responsável ficam órfãs, pelo
    atraso entre a revogação no antigo e a atribuição no novo. As demais continuam sem
    interrupção, com intervalos contíguos de épocas sucessivas."""
    _conferir(visoes, instantes, fim)
    historico: list[Intervalo] = []
    limites = [*instantes, fim]
    anterior: dict[str, str] = {}
    for epoca, (membros, inicio, proximo) in enumerate(zip(visoes, limites, limites[1:]), start=1):
        atual = atribuicao(particoes, membros)
        for particao, membro in atual.items():
            trocou = anterior.get(particao) != membro
            comeco = inicio + atraso if trocou else inicio
            historico.append(Intervalo(membro, particao, epoca, comeco, proximo, Fechamento.REVOGADA))
        anterior = atual
    return historico


def com_sobreposicao(
    historico: list[Intervalo],
    particao: str,
    intruso: str,
    inicio: int,
    duracao: int,
    epoca: int,
    fechamento: Fechamento = Fechamento.PERDIDA,
) -> list[Intervalo]:
    """Acrescenta um intervalo de posse de `intruso` sobre `particao`. Se o intervalo cruza
    a posse de outro trabalhador, o histórico resultante viola exclusividade por exatamente
    a interseção."""
    return [*historico, Intervalo(intruso, particao, epoca, inicio, inicio + duracao, fechamento)]


def _conferir(visoes: Sequence[Sequence[str]], instantes: Sequence[int], fim: int) -> None:
    if len(visoes) != len(instantes):
        raise ValueError("visoes e instantes precisam ter o mesmo tamanho")
    if list(instantes) != sorted(instantes):
        raise ValueError("instantes precisam ser crescentes")
    if instantes and fim < instantes[-1]:
        raise ValueError("fim anterior ao último rebalanceamento")
