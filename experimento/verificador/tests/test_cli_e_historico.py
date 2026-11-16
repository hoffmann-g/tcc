import json

import pytest

from verificador import sintetico
from verificador.cli import SAIDA_ENTRADA_INVALIDA, SAIDA_OK, SAIDA_VIOLACAO, main
from verificador.historico import Fechamento, HistoricoInvalido, Intervalo, escrever_csv, ler_csv

P = ["p0", "p1", "p2", "p3"]
VISOES = [["a", "b"], ["a", "b", "c"], ["a", "c"]]
T = [0, 10_000, 20_000]
FIM = 30_000


def test_csv_ida_e_volta(tmp_path):
    h = sintetico.cooperativo(P, VISOES, T, FIM, atraso=300)
    caminho = tmp_path / "h.csv"
    escrever_csv(caminho, h)
    assert ler_csv(caminho) == h


def test_csv_sem_coluna_falha(tmp_path):
    caminho = tmp_path / "h.csv"
    caminho.write_text("trabalhador,particao,inicio,fim\na,p0,0,1\n")
    with pytest.raises(HistoricoInvalido, match="epoca"):
        ler_csv(caminho)


def test_csv_com_fechamento_desconhecido_falha(tmp_path):
    caminho = tmp_path / "h.csv"
    caminho.write_text("trabalhador,particao,epoca,inicio,fim,fechamento\na,p0,1,0,1,sumiu\n")
    with pytest.raises(HistoricoInvalido, match="linha 2"):
        ler_csv(caminho)


def test_fim_antes_do_inicio_falha():
    with pytest.raises(HistoricoInvalido):
        Intervalo("a", "p0", 1, 10, 5, Fechamento.REVOGADA)


def test_cli_historico_correto_sai_zero(tmp_path, capsys):
    caminho = tmp_path / "h.csv"
    escrever_csv(caminho, sintetico.eager(P, VISOES, T, FIM, barreira=500))
    assert main([str(caminho)]) == SAIDA_OK
    saida = capsys.readouterr().out
    assert "exclusividade: ok" in saida
    assert "disponibilidade: ok" in saida


def test_cli_violacao_sai_dois_e_grava_json(tmp_path, capsys):
    base = sintetico.eager(P, VISOES, T, FIM, barreira=500)
    h = sintetico.com_sobreposicao(base, "p2", "a", inicio=18_000, duracao=5_000, epoca=1)
    caminho = tmp_path / "h.csv"
    escrever_csv(caminho, h)
    saida_json = tmp_path / "r.json"
    assert main([str(caminho), "--json", str(saida_json), "--quieto", "--janela", "0", str(FIM)]) == SAIDA_VIOLACAO
    assert capsys.readouterr().out == ""
    rel = json.loads(saida_json.read_text())
    assert rel["exclusividade"] is False
    assert rel["disponibilidade"] is True
    assert rel["sobreposicoes"][0]["duracao"] == 2_000
    assert rel["tempo_orfao"]["p0"]["total"] == 1_500


def test_cli_margem_e_janela(tmp_path):
    h = [
        Intervalo("a", "p0", 1, 0, 1_000, Fechamento.PERDIDA),
        Intervalo("b", "p0", 2, 900, 2_000, Fechamento.REVOGADA),
    ]
    caminho = tmp_path / "h.csv"
    escrever_csv(caminho, h)
    assert main([str(caminho), "--quieto"]) == SAIDA_VIOLACAO
    assert main([str(caminho), "--quieto", "--margem", "100"]) == SAIDA_OK
    # janela além do último fim deixa p0 órfã no fim
    assert main([str(caminho), "--quieto", "--margem", "100", "--janela", "0", "3000"]) == SAIDA_VIOLACAO


def test_cli_entrada_invalida_sai_um(tmp_path, capsys):
    caminho = tmp_path / "nao-existe.csv"
    assert main([str(caminho)]) == SAIDA_ENTRADA_INVALIDA
    assert "verificador:" in capsys.readouterr().err
