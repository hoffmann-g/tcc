"""Figuras para o volume, a partir de execuções gravadas.

Duas figuras. A linha do tempo de posse mostra, por partição, quem foi responsável em
cada instante, as sobreposições e as lacunas, em um painel por protocolo. A distribuição
das lacunas mostra a duração de cada lacuna de cobertura, por protocolo, acumulando
várias execuções.

Cores: paleta categórica validada (três primeiras posições), uma por trabalhador na
primeira figura e uma por protocolo na segunda; vermelho de estado reservado para a
sobreposição, que é uma violação. Texto e eixos em tinta neutra.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from orquestrador.montagem import AcaoExecutada, ler_acoes  # noqa: E402
from verificador.historico import Intervalo, ler_csv  # noqa: E402

SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
APAGADO = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
SUPERFICIE = "#fcfcfb"
CRITICO = "#d03b3b"

ORDEM = ("eager", "cooperativo", "kip848")
NOME = {"eager": "eager", "cooperativo": "cooperativo", "kip848": "KIP-848"}
ROTULO_ACAO = {
    "entrar": "{w} entra",
    "sair": "{w} sai",
    "matar": "{w} morto",
    "suspender": "{w} suspenso",
    "retomar": "{w} retomado",
}


@dataclass(frozen=True, slots=True)
class Execucao:
    pasta: Path
    info: dict
    intervalos: list[Intervalo]
    acoes: list[AcaoExecutada]
    relatorio: dict

    @property
    def protocolo(self) -> str:
        return self.info["protocolo"]

    def segundos(self, mono_ns: int) -> float:
        return (mono_ns - self.info["t0_mono_ns"]) / 1e9


def carregar(pasta: str | Path) -> Execucao:
    pasta = Path(pasta)
    return Execucao(
        pasta=pasta,
        info=json.loads((pasta / "execucao.json").read_text(encoding="utf-8")),
        intervalos=ler_csv(pasta / "historico.csv"),
        acoes=ler_acoes(pasta / "traco-executado.csv"),
        relatorio=json.loads((pasta / "relatorio.json").read_text(encoding="utf-8")),
    )


def _ptbr(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _estilo(eixo) -> None:
    eixo.set_facecolor(SUPERFICIE)
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eixo.spines[lado].set_color(EIXO)
        eixo.spines[lado].set_linewidth(0.8)
    eixo.tick_params(colors=TINTA_2, labelsize=7, length=3, width=0.8)
    eixo.grid(axis="x", color=GRADE, linewidth=0.6)
    eixo.set_axisbelow(True)


def _numero_particao(nome: str) -> int:
    return int(nome.rsplit("-", 1)[1])


def figura_linha_do_tempo(pastas: Iterable[str | Path], saida: Path, nome: str = "linha-do-tempo") -> list[Path]:
    """Um painel por execução (um protocolo cada), partições nas linhas, tempo no eixo x."""
    execucoes = sorted((carregar(p) for p in pastas), key=lambda e: ORDEM.index(e.protocolo))
    if not execucoes:
        raise ValueError("nenhuma execução informada")
    n_part = int(execucoes[0].info["particoes"])
    trabalhadores = list(execucoes[0].info["trabalhadores"])
    cor = {w: SERIES[i] for i, w in enumerate(trabalhadores)}

    fig, eixos = plt.subplots(
        len(execucoes), 1, sharex=True, figsize=(6.7, 1.75 * len(execucoes) + 0.9), dpi=200
    )
    eixos = np.atleast_1d(eixos)
    fig.patch.set_facecolor("white")

    for indice, (eixo, ex) in enumerate(zip(eixos, execucoes)):
        _estilo(eixo)
        duracao = float(ex.info["duracao_s"])
        rotulados: set[str] = set()
        for iv in sorted(ex.intervalos, key=lambda i: i.inicio):
            y = _numero_particao(iv.particao)
            s, f = ex.segundos(iv.inicio), ex.segundos(iv.fim)
            eixo.barh(y, f - s, left=s, height=0.62, color=cor[iv.trabalhador], edgecolor=SUPERFICIE, linewidth=0.8)
            if iv.trabalhador not in rotulados and f - s > 4:
                eixo.text(s + 0.6, y, iv.trabalhador, fontsize=6, color="white", va="center", ha="left")
                rotulados.add(iv.trabalhador)

        sobreposicoes = ex.relatorio["sobreposicoes"]
        for sob in sobreposicoes:
            y = _numero_particao(sob["particao"])
            s, f = ex.segundos(sob["inicio"]), ex.segundos(sob["fim"])
            eixo.plot([s, f], [y - 0.44, y - 0.44], color=CRITICO, linewidth=2, solid_capstyle="butt")
        if sobreposicoes:
            maior = max(sob["duracao"] for sob in sobreposicoes) / 1e9
            resumo = f"{len(sobreposicoes)} sobreposições, maior {_ptbr(maior)} s"
        else:
            resumo = "nenhuma sobreposição"

        for a in ex.acoes:
            if a.acao not in ROTULO_ACAO or a.t_planejado_s <= 0:
                continue
            x = ex.segundos(a.mono_ns)
            eixo.axvline(x, color=APAGADO, linewidth=0.7, linestyle=(0, (3, 3)), zorder=0)
            if indice == 0:
                eixo.annotate(
                    ROTULO_ACAO[a.acao].format(w=a.trabalhador),
                    xy=(x, 1.0),
                    xycoords=("data", "axes fraction"),
                    xytext=(2, 13),
                    textcoords="offset points",
                    fontsize=6,
                    color=TINTA_2,
                    rotation=90,
                    va="bottom",
                    ha="left",
                )

        eixo.set_yticks(range(n_part))
        eixo.set_yticklabels([f"p{i}" for i in range(n_part)])
        eixo.set_ylim(n_part - 0.5, -0.5)
        eixo.set_xlim(0, duracao)
        eixo.text(
            0.0, 1.02, f"{NOME[ex.protocolo]} — {resumo}",
            transform=eixo.transAxes, fontsize=7.5, color=TINTA, va="bottom", ha="left",
        )

    eixos[-1].set_xlabel("tempo desde o início da janela (s)", fontsize=7.5, color=TINTA_2)
    legenda = [Patch(facecolor=cor[w], label=w) for w in trabalhadores]
    legenda.append(Line2D([0], [0], color=CRITICO, linewidth=2, label="sobreposição de posse"))
    fig.legend(handles=legenda, loc="lower center", ncol=len(legenda), frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    return _salvar(fig, saida, nome)


def figura_lacunas(pastas: Iterable[str | Path], saida: Path, nome: str = "lacunas") -> list[Path]:
    """Duração de cada lacuna de cobertura, por protocolo, em escala logarítmica."""
    duracoes: dict[str, list[float]] = defaultdict(list)
    execucoes = Counter()
    for pasta in pastas:
        ex = carregar(pasta)
        execucoes[ex.protocolo] += 1
        for particao in ex.relatorio["tempo_orfao"].values():
            duracoes[ex.protocolo].extend(l["duracao"] / 1e9 for l in particao["lacunas"])
    protocolos = [p for p in ORDEM if p in duracoes]
    if not protocolos:
        raise ValueError("nenhuma execução informada")

    fig, eixo = plt.subplots(figsize=(6.7, 0.95 * len(protocolos) + 1.1), dpi=200)
    fig.patch.set_facecolor("white")
    _estilo(eixo)
    gerador = np.random.default_rng(1)
    transformacao = blended_transform_factory(eixo.transAxes, eixo.transData)
    for i, protocolo in enumerate(protocolos):
        valores = duracoes[protocolo]
        ys = i + gerador.uniform(-0.22, 0.22, len(valores))
        eixo.scatter(valores, ys, s=16, color=SERIES[i], alpha=0.7, edgecolor=SUPERFICIE, linewidth=0.4, zorder=3)
        mediana = statistics.median(valores)
        eixo.plot([mediana, mediana], [i - 0.36, i + 0.36], color=TINTA, linewidth=1.4, zorder=4)
        eixo.annotate(
            f"mediana {_ptbr(mediana, 2)} s",
            xy=(mediana, i - 0.38),
            xytext=(0, 2),
            textcoords="offset points",
            fontsize=6.5,
            color=TINTA_2,
            ha="center",
            va="bottom",
        )
        eixo.text(
            1.01, i, f"n = {len(valores)}\n{execucoes[protocolo]} exec.",
            transform=transformacao, fontsize=6.5, color=TINTA_2, va="center", ha="left",
        )

    eixo.set_xscale("log")
    eixo.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _ptbr(v, 2 if v < 0.1 else (1 if v < 10 else 0))))
    eixo.set_yticks(range(len(protocolos)))
    eixo.set_yticklabels([NOME[p] for p in protocolos], fontsize=8, color=TINTA)
    eixo.set_ylim(len(protocolos) - 0.5, -0.6)
    eixo.set_xlabel("duração da lacuna de cobertura (s), escala logarítmica", fontsize=7.5, color=TINTA_2)
    fig.tight_layout(rect=(0, 0, 0.9, 1))
    return _salvar(fig, saida, nome)


def _salvar(fig, saida: Path, nome: str) -> list[Path]:
    saida.mkdir(parents=True, exist_ok=True)
    caminhos = [saida / f"{nome}.png", saida / f"{nome}.svg"]
    for caminho in caminhos:
        fig.savefig(caminho, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return caminhos
