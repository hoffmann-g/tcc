from verificador import sintetico
from verificador.disponibilidade import Lacuna, cobertura, distribuicao
from verificador.historico import Fechamento, Intervalo

P = ["p0", "p1", "p2", "p3"]
VISOES = [["a", "b"], ["a", "b", "c"], ["a", "c"]]
T = [0, 10_000, 20_000]
FIM = 30_000


def test_eager_tempo_orfao_e_uma_barreira_por_visao_em_toda_particao():
    h = sintetico.eager(P, VISOES, T, FIM, barreira=500)
    cob = cobertura(h, janela=(0, FIM))
    assert set(cob) == set(P)
    for c in cob.values():
        assert c.tempo_orfao == 3 * 500
        assert len(c.lacunas) == 3
        assert c.coberta_no_fim


def test_cooperativo_so_particoes_transferidas_ficam_orfas():
    h = sintetico.cooperativo(P, VISOES, T, FIM, atraso=300)
    cob = cobertura(h, janela=(0, FIM))
    # visão 1: todas entram (300 cada). visão 2: [a,b] -> [a,b,c] move p2 (a->c) e p3 (b->a).
    # visão 3: [a,b,c] -> [a,c] move p1 (b->c), p2 (c->a) e p3 (a->c).
    assert cob["p0"].tempo_orfao == 300
    assert cob["p1"].tempo_orfao == 600
    assert cob["p2"].tempo_orfao == 900
    assert cob["p3"].tempo_orfao == 900


def test_particao_sem_intervalos_fica_orfa_na_janela_inteira():
    h = [Intervalo("a", "p0", 1, 0, 100, Fechamento.REVOGADA)]
    cob = cobertura(h, janela=(0, 100), particoes=["p0", "p9"])
    assert cob["p0"].tempo_orfao == 0
    assert cob["p9"].lacunas == (Lacuna(0, 100),)
    assert not cob["p9"].coberta_no_fim


def test_janela_recorta_intervalos():
    h = [Intervalo("a", "p0", 1, 0, 1_000, Fechamento.REVOGADA)]
    cob = cobertura(h, janela=(200, 1_500))
    assert cob["p0"].lacunas == (Lacuna(1_000, 1_500),)
    assert cob["p0"].tempo_orfao == 500
    assert not cob["p0"].coberta_no_fim


def test_posses_sobrepostas_contam_uma_vez_na_cobertura():
    h = [
        Intervalo("a", "p0", 1, 0, 600, Fechamento.PERDIDA),
        Intervalo("b", "p0", 2, 400, 1_000, Fechamento.REVOGADA),
    ]
    assert cobertura(h, janela=(0, 1_000))["p0"].tempo_orfao == 0


def test_intervalo_aberto_cobre_ate_o_fim_da_janela():
    h = [Intervalo("a", "p0", 1, 0, 1_000, Fechamento.JANELA)]
    c = cobertura(h, janela=(0, 1_000))["p0"]
    assert c.tempo_orfao == 0 and c.coberta_no_fim


def test_distribuicao():
    d = distribuicao([300, 100, 200, 400, 500])
    assert (d.quantidade, d.total, d.minimo, d.maximo) == (5, 1_500, 100, 500)
    assert d.mediana == 300
    assert d.p90 == 500
    vazia = distribuicao([])
    assert vazia.quantidade == 0 and vazia.mediana is None
