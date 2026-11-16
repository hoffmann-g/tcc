"""Linha de comando do verificador.

Código de saída: 0 quando exclusividade e disponibilidade valem; 2 quando alguma é
violada; 1 quando a entrada é inválida.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from verificador.historico import HistoricoInvalido, ler_csv
from verificador.relatorio import relatorio

SAIDA_OK = 0
SAIDA_ENTRADA_INVALIDA = 1
SAIDA_VIOLACAO = 2


def analisador() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verificador",
        description=(
            "Verifica exclusividade e disponibilidade em um histórico de posse "
            "(CSV: trabalhador, particao, epoca, inicio, fim, fechamento; instantes em ns)."
        ),
    )
    p.add_argument("historico", type=Path, help="arquivo CSV do histórico")
    p.add_argument(
        "--janela",
        nargs=2,
        type=int,
        metavar=("T0", "T1"),
        help="janela de observação em ns; padrão: do menor início ao maior fim",
    )
    p.add_argument(
        "--margem",
        type=int,
        default=0,
        help="erro da base de tempo em ns; sobreposições com duração até esse valor não são reportadas",
    )
    p.add_argument(
        "--particoes",
        help="lista de partições separadas por vírgula; as ausentes do histórico ficam órfãs na janela inteira",
    )
    p.add_argument("--json", type=Path, metavar="ARQUIVO", help="grava o relatório completo em JSON")
    p.add_argument("--quieto", action="store_true", help="não imprime o relatório em texto")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = analisador().parse_args(argv)
    try:
        intervalos = ler_csv(args.historico)
        particoes = args.particoes.split(",") if args.particoes else None
        janela = tuple(args.janela) if args.janela else None
        rel = relatorio(intervalos, janela=janela, margem=args.margem, particoes=particoes)
    except (HistoricoInvalido, ValueError, OSError) as erro:
        print(f"verificador: {erro}", file=sys.stderr)
        return SAIDA_ENTRADA_INVALIDA

    if not args.quieto:
        print(rel.texto())
    if args.json:
        args.json.write_text(json.dumps(rel.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return SAIDA_OK if rel.exclusividade and rel.disponibilidade else SAIDA_VIOLACAO


if __name__ == "__main__":
    sys.exit(main())
