"""Relatório de um histórico: exclusividade, disponibilidade e intervalos abertos."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from verificador.disponibilidade import Cobertura, Distribuicao, cobertura, distribuicao
from verificador.exclusividade import Sobreposicao, sobreposicoes
from verificador.historico import Fechamento, Intervalo, janela_padrao, trabalhadores


def segundos(ns: int | None) -> str:
    return "—" if ns is None else f"{ns / 1e9:.3f} s"


@dataclass(frozen=True, slots=True)
class Relatorio:
    janela: tuple[int, int]
    margem: int
    intervalos: int
    trabalhadores: int
    abertos: tuple[Intervalo, ...]
    sobreposicoes: tuple[Sobreposicao, ...]
    coberturas: dict[str, Cobertura]

    @property
    def exclusividade(self) -> bool:
        return not self.sobreposicoes

    @property
    def disponibilidade(self) -> bool:
        return all(c.coberta_no_fim for c in self.coberturas.values())

    @property
    def lacunas(self) -> Distribuicao:
        return distribuicao(l.duracao for c in self.coberturas.values() for l in c.lacunas)

    def para_dict(self) -> dict[str, Any]:
        return {
            "janela": {"inicio": self.janela[0], "fim": self.janela[1]},
            "margem": self.margem,
            "intervalos": self.intervalos,
            "particoes": len(self.coberturas),
            "trabalhadores": self.trabalhadores,
            "exclusividade": self.exclusividade,
            "disponibilidade": self.disponibilidade,
            "sobreposicoes": [
                {
                    "particao": s.particao,
                    "trabalhadores": [s.a.trabalhador, s.b.trabalhador],
                    "epocas": [s.a.epoca, s.b.epoca],
                    "fechamentos": [s.a.fechamento.value, s.b.fechamento.value],
                    "inicio": s.inicio,
                    "fim": s.fim,
                    "duracao": s.duracao,
                }
                for s in self.sobreposicoes
            ],
            "tempo_orfao": {
                p: {
                    "total": c.tempo_orfao,
                    "fracao": c.fracao_orfa,
                    "coberta_no_fim": c.coberta_no_fim,
                    "lacunas": [{"inicio": l.inicio, "fim": l.fim, "duracao": l.duracao} for l in c.lacunas],
                }
                for p, c in self.coberturas.items()
            },
            "lacunas": asdict(self.lacunas),
            "abertos": [i.linha() for i in self.abertos],
        }

    def texto(self) -> str:
        linhas: list[str] = []
        largura = self.janela[1] - self.janela[0]
        linhas.append(
            f"histórico: {self.intervalos} intervalos, {len(self.coberturas)} partições, "
            f"{self.trabalhadores} trabalhadores"
        )
        linhas.append(f"janela: [{self.janela[0]}, {self.janela[1]}) ns ({segundos(largura)})")
        linhas.append(f"margem: {self.margem} ns")
        linhas.append("")

        if self.exclusividade:
            linhas.append("exclusividade: ok, nenhuma sobreposição acima da margem")
        else:
            maior = max(s.duracao for s in self.sobreposicoes)
            linhas.append(
                f"exclusividade: VIOLADA, {len(self.sobreposicoes)} sobreposições, "
                f"maior {segundos(maior)}"
            )
            for s in self.sobreposicoes:
                linhas.append(
                    f"  {s.particao:<12} {s.a.trabalhador} (e={s.a.epoca}, {s.a.fechamento.value}) "
                    f"× {s.b.trabalhador} (e={s.b.epoca}, {s.b.fechamento.value})  "
                    f"[{s.inicio}, {s.fim})  {segundos(s.duracao)}"
                )
        linhas.append("")

        if self.disponibilidade:
            linhas.append("disponibilidade: ok, todas as partições cobertas no fim da janela")
        else:
            orfas = [p for p, c in self.coberturas.items() if not c.coberta_no_fim]
            linhas.append(f"disponibilidade: VIOLADA, órfãs no fim da janela: {', '.join(orfas)}")
        linhas.append("tempo órfão por partição:")
        for p, c in self.coberturas.items():
            linhas.append(
                f"  {p:<12} {segundos(c.tempo_orfao):>12}  ({c.fracao_orfa:6.2%})  "
                f"{len(c.lacunas)} lacunas"
            )
        d = self.lacunas
        linhas.append(
            f"  lacunas: {d.quantidade}, total {segundos(d.total)}, mediana {segundos(d.mediana)}, "
            f"p90 {segundos(d.p90)}, máx {segundos(d.maximo)}"
        )
        linhas.append("")
        linhas.append(f"intervalos abertos no fim da janela: {len(self.abertos)}")
        for i in self.abertos:
            linhas.append(f"  {i.particao:<12} {i.trabalhador} (e={i.epoca}) desde {i.inicio}")
        return "\n".join(linhas)


def relatorio(
    intervalos: list[Intervalo],
    janela: tuple[int, int] | None = None,
    margem: int = 0,
    particoes: Sequence[str] | None = None,
) -> Relatorio:
    janela = janela or janela_padrao(intervalos)
    return Relatorio(
        janela=janela,
        margem=margem,
        intervalos=len(intervalos),
        trabalhadores=len(trabalhadores(intervalos)),
        abertos=tuple(i for i in intervalos if i.fechamento is Fechamento.JANELA),
        sobreposicoes=tuple(sobreposicoes(intervalos, margem)),
        coberturas=cobertura(intervalos, janela, particoes),
    )
