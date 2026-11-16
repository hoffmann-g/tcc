import pytest

from orquestrador.traco import Acao, TracoInvalido, construir


def base(**extra):
    dados = {
        "nome": "t",
        "particoes": 4,
        "duracao_s": 60,
        "eventos": [
            {"t": 0, "acao": "entrar", "trabalhador": "w1"},
            {"t": 0, "acao": "entrar", "trabalhador": "w2"},
            {"t": 10, "acao": "suspender", "trabalhador": "w2", "duracao": 20},
            {"t": 40, "acao": "sair", "trabalhador": "w2"},
            {"t": 50, "acao": "matar", "trabalhador": "w1"},
        ],
    }
    dados.update(extra)
    return dados


def test_traco_valido_ordena_eventos_e_lista_trabalhadores():
    dados = base()
    dados["eventos"].reverse()
    t = construir(dados)
    assert [e.t for e in t.eventos] == [0, 0, 10, 40, 50]
    assert t.trabalhadores == ["w1", "w2"] or t.trabalhadores == ["w2", "w1"]
    assert t.eventos[2].acao is Acao.SUSPENDER and t.eventos[2].duracao == 20


@pytest.mark.parametrize(
    "eventos, trecho",
    [
        ([{"t": 0, "acao": "sair", "trabalhador": "w1"}], "sem estar em execução"),
        ([{"t": 0, "acao": "entrar", "trabalhador": "w1"}, {"t": 1, "acao": "entrar", "trabalhador": "w1"}], "mais de uma vez"),
        ([{"t": 0, "acao": "entrar", "trabalhador": "w1"}, {"t": 1, "acao": "suspender", "trabalhador": "w1"}], "exige duracao"),
        ([{"t": 0, "acao": "entrar", "trabalhador": "w1"}, {"t": 50, "acao": "suspender", "trabalhador": "w1", "duracao": 20}], "depois do fim"),
        (
            [
                {"t": 0, "acao": "entrar", "trabalhador": "w1"},
                {"t": 1, "acao": "suspender", "trabalhador": "w1", "duracao": 20},
                {"t": 5, "acao": "sair", "trabalhador": "w1"},
            ],
            "enquanto suspenso",
        ),
        ([{"t": 60, "acao": "entrar", "trabalhador": "w1"}], "fora de"),
        ([{"t": 0, "acao": "voar", "trabalhador": "w1"}], "evento 1"),
        ([], "sem eventos"),
    ],
)
def test_tracos_invalidos(eventos, trecho):
    with pytest.raises(TracoInvalido, match=trecho):
        construir(base(eventos=eventos))


def test_matar_durante_suspensao_e_permitido():
    eventos = [
        {"t": 0, "acao": "entrar", "trabalhador": "w1"},
        {"t": 1, "acao": "suspender", "trabalhador": "w1", "duracao": 20},
        {"t": 5, "acao": "matar", "trabalhador": "w1"},
    ]
    construir(base(eventos=eventos))


def test_campo_obrigatorio_ausente():
    dados = base()
    del dados["particoes"]
    with pytest.raises(TracoInvalido, match="particoes"):
        construir(dados)
