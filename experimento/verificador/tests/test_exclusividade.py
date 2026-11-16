from verificador import sintetico
from verificador.exclusividade import sobreposicoes
from verificador.historico import Fechamento, Intervalo

P = ["p0", "p1", "p2", "p3"]
VISOES = [["a", "b"], ["a", "b", "c"], ["a", "c"]]
T = [0, 10_000, 20_000]
FIM = 30_000


def test_eager_ideal_nao_tem_sobreposicao():
    assert sobreposicoes(sintetico.eager(P, VISOES, T, FIM, barreira=500)) == []


def test_cooperativo_ideal_nao_tem_sobreposicao():
    assert sobreposicoes(sintetico.cooperativo(P, VISOES, T, FIM, atraso=300)) == []


def test_intervalos_contiguos_nao_se_sobrepoem():
    h = [
        Intervalo("a", "p0", 1, 0, 10, Fechamento.REVOGADA),
        Intervalo("b", "p0", 2, 10, 20, Fechamento.REVOGADA),
    ]
    assert sobreposicoes(h) == []


def test_sobreposicao_plantada_tem_duracao_exata():
    base = sintetico.eager(P, VISOES, T, FIM, barreira=500)
    # na visão 2 (época 2), p2 pertence a c durante [10_500, 20_000)
    h = sintetico.com_sobreposicao(base, "p2", "a", inicio=18_000, duracao=5_000, epoca=1)
    [s] = sobreposicoes(h)
    assert s.particao == "p2"
    assert {s.a.trabalhador, s.b.trabalhador} == {"a", "c"}
    assert (s.inicio, s.fim) == (18_000, 20_000)
    assert s.duracao == 2_000


def test_intruso_cruzando_duas_posses_gera_duas_sobreposicoes():
    base = sintetico.eager(P, VISOES, T, FIM, barreira=500)
    # p0 pertence a `a` em todas as visões; `z` entra cruzando as épocas 1 e 2
    h = sintetico.com_sobreposicao(base, "p0", "z", inicio=9_000, duracao=3_000, epoca=9)
    s = sobreposicoes(h)
    assert [(x.inicio, x.fim) for x in s] == [(9_000, 10_000), (10_500, 12_000)]


def test_mesmo_trabalhador_em_epocas_distintas_nao_e_violacao():
    h = [
        Intervalo("a", "p0", 1, 0, 100, Fechamento.PERDIDA),
        Intervalo("a", "p0", 2, 50, 150, Fechamento.REVOGADA),
    ]
    assert sobreposicoes(h) == []


def test_margem_suprime_sobreposicoes_curtas():
    h = [
        Intervalo("a", "p0", 1, 0, 1_000, Fechamento.PERDIDA),
        Intervalo("b", "p0", 2, 900, 2_000, Fechamento.REVOGADA),
    ]
    assert len(sobreposicoes(h, margem=0)) == 1
    assert len(sobreposicoes(h, margem=99)) == 1
    assert sobreposicoes(h, margem=100) == []
    assert sobreposicoes(h, margem=1_000) == []


def test_intervalo_aberto_na_janela_nao_entra_na_sobreposicao():
    h = [
        Intervalo("a", "p0", 1, 0, 1_000, Fechamento.JANELA),
        Intervalo("b", "p0", 2, 500, 1_000, Fechamento.REVOGADA),
    ]
    assert sobreposicoes(h) == []


def test_resultado_ordenado_por_particao_e_inicio():
    h = [
        Intervalo("a", "p1", 1, 0, 100, Fechamento.PERDIDA),
        Intervalo("b", "p1", 2, 50, 150, Fechamento.REVOGADA),
        Intervalo("a", "p0", 1, 0, 100, Fechamento.PERDIDA),
        Intervalo("b", "p0", 2, 20, 150, Fechamento.REVOGADA),
    ]
    assert [(s.particao, s.inicio) for s in sobreposicoes(h)] == [("p0", 20), ("p1", 50)]
