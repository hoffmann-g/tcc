from orquestrador.montagem import AcaoExecutada, EventoColetor, montar
from verificador.historico import Fechamento, Intervalo

T0, T1 = 1_000, 100_000


def acao(t, nome, w="", mono=0, relogio=0, pid=None):
    return AcaoExecutada(t, nome, w, mono, relogio, pid, "")


def ev(nome, w, p, epoca, mono, relogio=0):
    return EventoColetor(nome, w, p, epoca, mono, relogio)


ACOES = [
    acao(0, "inicio", mono=T0, relogio=5_000_000_000),
    acao(0, "entrar", "w1", mono=1_100, relogio=5_000_000_100, pid=11),
    acao(0, "entrar", "w2", mono=1_200, relogio=5_000_000_200, pid=12),
    acao(50, "matar", "w1", mono=60_000, relogio=5_000_058_900, pid=11),
    acao(90, "fim", mono=T1, relogio=5_000_099_000),
]


def test_fechamentos_revogada_externo_e_janela():
    eventos = [
        ev("processo_inicio", "w1", "", -1, 2_000, 5_000_001_000),
        ev("atribuida", "w1", "t-0", 1, 3_000),
        ev("atribuida", "w2", "t-1", 1, 3_100),
        ev("revogada", "w2", "t-1", 1, 40_000),
        ev("atribuida", "w2", "t-1", 2, 41_000),
        ev("atribuida", "w2", "t-0", 3, 70_000),
    ]
    m = montar(eventos, ACOES, T0, T1)
    assert m.anomalias == []
    assert m.intervalos == [
        Intervalo("w1", "t-0", 1, 3_000, 60_000, Fechamento.EXTERNO),
        Intervalo("w2", "t-0", 3, 70_000, T1, Fechamento.JANELA),
        Intervalo("w2", "t-1", 1, 3_100, 40_000, Fechamento.REVOGADA),
        Intervalo("w2", "t-1", 2, 41_000, T1, Fechamento.JANELA),
    ]


def test_epoca_do_intervalo_e_a_da_atribuicao():
    eventos = [
        ev("atribuida", "w2", "t-0", 7, 3_000),
        ev("perdida", "w2", "t-0", 0, 9_000),  # época já reposta no callback de perda
    ]
    [i] = montar(eventos, ACOES, T0, T1).intervalos
    assert i.epoca == 7 and i.fechamento is Fechamento.PERDIDA


def test_evento_depois_da_morte_e_anomalia_e_nao_entra():
    eventos = [
        ev("atribuida", "w1", "t-0", 1, 3_000),
        ev("revogada", "w1", "t-0", 1, 61_000),
    ]
    m = montar(eventos, ACOES, T0, T1)
    assert len(m.anomalias) == 1 and "depois da morte" in m.anomalias[0]
    assert m.intervalos == [Intervalo("w1", "t-0", 1, 3_000, 60_000, Fechamento.EXTERNO)]


def test_evento_sem_particao_e_ignorado_com_anomalia():
    eventos = [
        ev("revogada", "w2", "", 2, 5_000),
        ev("atribuida", "w2", "t-0", 2, 6_000),
    ]
    m = montar(eventos, ACOES, T0, T1)
    assert m.intervalos == [Intervalo("w2", "t-0", 2, 6_000, T1, Fechamento.JANELA)]
    assert len(m.anomalias) == 1 and "sem partição" in m.anomalias[0]


def test_fechamento_sem_abertura_e_anomalia():
    m = montar([ev("revogada", "w2", "t-5", 1, 5_000)], ACOES, T0, T1)
    assert m.intervalos == [] and "sem atribuição aberta" in m.anomalias[0]


def test_atribuicao_dupla_fecha_a_anterior_e_registra_anomalia():
    eventos = [
        ev("atribuida", "w2", "t-0", 1, 3_000),
        ev("atribuida", "w2", "t-0", 2, 8_000),
        ev("revogada", "w2", "t-0", 2, 9_000),
    ]
    m = montar(eventos, ACOES, T0, T1)
    assert "atribuição dupla" in m.anomalias[0]
    assert m.intervalos == [
        Intervalo("w2", "t-0", 1, 3_000, 8_000, Fechamento.REVOGADA),
        Intervalo("w2", "t-0", 2, 8_000, 9_000, Fechamento.REVOGADA),
    ]


def test_eventos_fora_da_janela_sao_ignorados():
    eventos = [
        ev("atribuida", "w2", "t-0", 1, 3_000),
        ev("revogada", "w2", "t-0", 1, 100_500),  # depois de T1
    ]
    m = montar(eventos, ACOES, T0, T1)
    assert m.intervalos == [Intervalo("w2", "t-0", 1, 3_000, T1, Fechamento.JANELA)]


def test_base_de_tempo():
    eventos = [
        # coletor w1 leu mono 2_000 e relógio 5_000_001_000; orquestrador lançou em 1_100 / 5_000_000_100
        ev("processo_inicio", "w1", "", -1, 2_000, 5_000_001_000),
        # w2 com 250 ns de desvio
        ev("processo_inicio", "w2", "", -1, 2_450, 5_000_001_400),
    ]
    m = montar(eventos, ACOES, T0, T1)
    assert {b.trabalhador: b.desvio_ns for b in m.base_tempo} == {"w1": 0, "w2": 50}
    assert m.erro_base_tempo_ns == 50
