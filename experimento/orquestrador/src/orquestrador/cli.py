"""Linha de comando do orquestrador.

    orquestrador validar  TRACO.toml
    orquestrador executar TRACO.toml --protocolo eager|cooperativo|kip848
    orquestrador montar   PASTA_DA_EXECUCAO
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from orquestrador import comparacao, montagem, traco
from orquestrador.execucao import PROTOCOLOS, ErroExecucao, Parametros, executar

EXPERIMENTO = Path(__file__).resolve().parents[3]


def analisador() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orquestrador", description="Aplica traços de churn a um agrupamento Kafka.")
    sub = p.add_subparsers(dest="comando", required=True)

    v = sub.add_parser("validar", help="confere um traço sem executar")
    v.add_argument("traco", type=Path)

    e = sub.add_parser("executar", help="executa um traço com um protocolo")
    e.add_argument("traco", type=Path)
    e.add_argument("--protocolo", required=True, choices=PROTOCOLOS)
    e.add_argument("--saida", type=Path, default=EXPERIMENTO / "execucoes", help="pasta das execuções")
    e.add_argument("--coletor", type=Path, default=EXPERIMENTO / "coletor", help="pasta do coletor compilado")
    e.add_argument("--bootstrap", default="localhost:9092")
    e.add_argument("--container", default="tcc-kafka", help="nome do contêiner do broker")
    e.add_argument("--sessao-ms", type=int, default=10_000, help="só vale no protocolo clássico")
    e.add_argument("--heartbeat-ms", type=int, default=3_000, help="só vale no protocolo clássico")
    e.add_argument("--poll-ms", type=int, default=500)
    e.add_argument("--trabalho-ms", type=int, default=0, help="processamento simulado por registro")

    m = sub.add_parser("montar", help="remonta o histórico e o relatório de uma execução gravada")
    m.add_argument("pasta", type=Path)

    c = sub.add_parser("comparar", help="tabela com uma linha por execução gravada")
    c.add_argument("pastas", type=Path, nargs="+")
    c.add_argument("--csv", type=Path, metavar="ARQUIVO", help="grava a tabela também em CSV")
    c.add_argument("--agregar", action="store_true", help="resume por traço e protocolo: mediana [mín; máx] entre execuções")

    f = sub.add_parser("figuras", help="gera as figuras do volume em PNG e SVG")
    f.add_argument("--linha-do-tempo", type=Path, nargs="+", metavar="PASTA", help="uma execução por protocolo")
    f.add_argument("--lacunas", type=Path, nargs="+", metavar="PASTA", help="execuções a acumular por protocolo")
    f.add_argument("--saida", type=Path, default=EXPERIMENTO.parent / "volume-1" / "figuras")
    f.add_argument("--sufixo", default="", help="acrescentado ao nome dos arquivos, por exemplo -piloto")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = analisador().parse_args(argv)
    try:
        if args.comando == "validar":
            t = traco.carregar(args.traco)
            print(f"{t.nome}: {t.particoes} partições, {t.duracao_s:g} s, {len(t.eventos)} eventos, "
                  f"trabalhadores {', '.join(t.trabalhadores)}")
            return 0
        if args.comando == "executar":
            t = traco.carregar(args.traco)
            params = Parametros(
                protocolo=args.protocolo,
                coletor=args.coletor.resolve(),
                saida=args.saida.resolve(),
                bootstrap=args.bootstrap,
                container=args.container,
                sessao_ms=args.sessao_ms,
                heartbeat_ms=args.heartbeat_ms,
                poll_ms=args.poll_ms,
                trabalho_ms=args.trabalho_ms,
            )
            pasta = executar(t, params)
            print((pasta / "relatorio.txt").read_text(encoding="utf-8"))
            print(f"execução gravada em {pasta}")
            return 0
        if args.comando == "montar":
            m, rel = montagem.montar_execucao(args.pasta)
            print(rel.texto())
            if m.anomalias:
                print("\nanomalias:")
                for a in m.anomalias:
                    print(f"  {a}")
            return 0
        if args.comando == "comparar":
            linhas = comparacao.comparar(args.pastas)
            if args.agregar:
                print(comparacao.tabela_agregada_markdown(comparacao.agregar(linhas)))
            else:
                print(comparacao.tabela_markdown(linhas))
            if args.csv:
                args.csv.write_text(comparacao.tabela_csv(linhas), encoding="utf-8")
            return 0
        if args.comando == "figuras":
            from orquestrador import analise

            if not args.linha_do_tempo and not args.lacunas:
                print("orquestrador: informe --linha-do-tempo e/ou --lacunas", file=sys.stderr)
                return 1
            gerados: list[Path] = []
            if args.linha_do_tempo:
                gerados += analise.figura_linha_do_tempo(args.linha_do_tempo, args.saida, f"linha-do-tempo{args.sufixo}")
            if args.lacunas:
                gerados += analise.figura_lacunas(args.lacunas, args.saida, f"lacunas{args.sufixo}")
            for g in gerados:
                print(g)
            return 0
    except (traco.TracoInvalido, ErroExecucao, FileNotFoundError) as erro:
        print(f"orquestrador: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
