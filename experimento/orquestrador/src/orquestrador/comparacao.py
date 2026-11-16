"""Comparação entre execuções gravadas: uma linha por execução com as grandezas do
relatório do verificador e da montagem."""

from __future__ import annotations

import csv
import io
import json
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Linha:
    execucao: str
    traco: str
    protocolo: str
    intervalos: int
    sobreposicoes: int
    maior_sobreposicao_ns: int
    soma_sobreposicoes_ns: int
    orfao_total_ns: int
    lacunas: int
    lacuna_mediana_ns: int | None
    lacuna_p90_ns: int | None
    lacuna_max_ns: int | None
    abertos: int
    anomalias: int
    erro_base_tempo_ns: int


def ler(pasta: str | Path) -> Linha:
    pasta = Path(pasta)
    info = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
    rel = json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))
    mont = json.loads((pasta / "montagem.json").read_text(encoding="utf-8"))
    sob = rel["sobreposicoes"]
    lac = rel["lacunas"]
    return Linha(
        execucao=pasta.name,
        traco=info["nome"],
        protocolo=info["protocolo"],
        intervalos=rel["intervalos"],
        sobreposicoes=len(sob),
        maior_sobreposicao_ns=max((s["duracao"] for s in sob), default=0),
        soma_sobreposicoes_ns=sum(s["duracao"] for s in sob),
        orfao_total_ns=sum(p["total"] for p in rel["tempo_orfao"].values()),
        lacunas=lac["quantidade"],
        lacuna_mediana_ns=lac["mediana"],
        lacuna_p90_ns=lac["p90"],
        lacuna_max_ns=lac["maximo"],
        abertos=len(rel["abertos"]),
        anomalias=len(mont["anomalias"]),
        erro_base_tempo_ns=mont["erro_base_tempo_ns"],
    )


def comparar(pastas: Iterable[str | Path]) -> list[Linha]:
    """Uma linha por pasta de execução; entradas que não são pastas são ignoradas, para
    que um glob sobre a pasta de execuções possa incluir arquivos soltos."""
    linhas = [ler(p) for p in pastas if Path(p).is_dir()]
    ordem = {"eager": 0, "cooperativo": 1, "kip848": 2}
    linhas.sort(key=lambda l: (l.traco, ordem.get(l.protocolo, 9), l.execucao))
    return linhas


@dataclass(frozen=True, slots=True)
class Agregado:
    """Resumo de várias execuções do mesmo traço com o mesmo protocolo."""

    traco: str
    protocolo: str
    execucoes: int
    sobreposicoes_por_execucao: tuple[int, ...]
    maior_sobreposicao_ns: tuple[int, int, int]  # mínimo, mediana, máximo entre execuções
    orfao_total_ns: tuple[int, int, int]
    lacunas_por_execucao: tuple[int, int, int]
    lacuna_mediana_ns: tuple[int, int, int]
    lacuna_max_ns: tuple[int, int, int]
    anomalias: int
    erro_base_tempo_ns: int


def _tres(valores: list[int]) -> tuple[int, int, int]:
    ordenados = sorted(valores)
    return ordenados[0], int(statistics.median(ordenados)), ordenados[-1]


def agregar(linhas: list[Linha]) -> list[Agregado]:
    grupos: dict[tuple[str, str], list[Linha]] = {}
    for l in linhas:
        grupos.setdefault((l.traco, l.protocolo), []).append(l)
    ordem = {"eager": 0, "cooperativo": 1, "kip848": 2}
    resultado = []
    for (traco, protocolo), ls in sorted(grupos.items(), key=lambda kv: (kv[0][0], ordem.get(kv[0][1], 9))):
        resultado.append(
            Agregado(
                traco=traco,
                protocolo=protocolo,
                execucoes=len(ls),
                sobreposicoes_por_execucao=tuple(l.sobreposicoes for l in ls),
                maior_sobreposicao_ns=_tres([l.maior_sobreposicao_ns for l in ls]),
                orfao_total_ns=_tres([l.orfao_total_ns for l in ls]),
                lacunas_por_execucao=_tres([l.lacunas for l in ls]),
                lacuna_mediana_ns=_tres([l.lacuna_mediana_ns or 0 for l in ls]),
                lacuna_max_ns=_tres([l.lacuna_max_ns or 0 for l in ls]),
                anomalias=sum(l.anomalias for l in ls),
                erro_base_tempo_ns=max(l.erro_base_tempo_ns for l in ls),
            )
        )
    return resultado


def _faixa(tres: tuple[int, int, int]) -> str:
    minimo, mediana, maximo = tres
    return f"{_s(mediana)} [{_s(minimo)}; {_s(maximo)}]"


def tabela_agregada_markdown(agregados: list[Agregado]) -> str:
    cabecalho = (
        "| traço | protocolo | exec. | sobrep. por exec. | maior sobrep. (s) | órfão total (s) | "
        "lacunas por exec. | lacuna mediana (s) | lacuna máx (s) | anomalias | erro base (µs) |"
    )
    sep = "|" + "---|" * 11
    corpo = [
        f"| {a.traco} | {a.protocolo} | {a.execucoes} | "
        f"{', '.join(str(n) for n in a.sobreposicoes_por_execucao)} | "
        f"{_faixa(a.maior_sobreposicao_ns)} | {_faixa(a.orfao_total_ns)} | "
        f"{a.lacunas_por_execucao[1]} [{a.lacunas_por_execucao[0]}; {a.lacunas_por_execucao[2]}] | "
        f"{_faixa(a.lacuna_mediana_ns)} | {_faixa(a.lacuna_max_ns)} | {a.anomalias} | "
        f"{a.erro_base_tempo_ns / 1e3:.0f} |"
        for a in agregados
    ]
    nota = "Valores: mediana [mínimo; máximo] entre execuções."
    return "\n".join([cabecalho, sep, *corpo, "", nota])


def _s(ns: int | None) -> str:
    return "—" if ns is None else f"{ns / 1e9:.3f}"


def tabela_markdown(linhas: list[Linha]) -> str:
    cabecalho = (
        "| traço | protocolo | sobrep. | maior (s) | soma (s) | órfão total (s) | lacunas | "
        "mediana (s) | p90 (s) | máx (s) | abertos | anomalias | erro base (µs) |"
    )
    sep = "|" + "---|" * 13
    corpo = [
        f"| {l.traco} | {l.protocolo} | {l.sobreposicoes} | {_s(l.maior_sobreposicao_ns)} | "
        f"{_s(l.soma_sobreposicoes_ns)} | {_s(l.orfao_total_ns)} | {l.lacunas} | "
        f"{_s(l.lacuna_mediana_ns)} | {_s(l.lacuna_p90_ns)} | {_s(l.lacuna_max_ns)} | "
        f"{l.abertos} | {l.anomalias} | {l.erro_base_tempo_ns / 1e3:.0f} |"
        for l in linhas
    ]
    return "\n".join([cabecalho, sep, *corpo])


def tabela_csv(linhas: list[Linha]) -> str:
    saida = io.StringIO()
    nomes = [f.name for f in fields(Linha)]
    escritor = csv.DictWriter(saida, fieldnames=nomes)
    escritor.writeheader()
    for l in linhas:
        escritor.writerow({n: getattr(l, n) for n in nomes})
    return saida.getvalue()
