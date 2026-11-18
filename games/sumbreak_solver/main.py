#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from games.sumbreak_solver.src.sumbreak_solver import SumbreakSolver


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve a LinkedIn Sumbreak board given as JSON (null for empty cells).")
    parser.add_argument("board", help='JSON rows, for example "[[1, 1, 64], [4, 2, 32], [4, 4, 16]]"')
    args = parser.parse_args()

    try:
        board = json.loads(args.board)
    except json.JSONDecodeError as exc:
        print(f"Board is not valid JSON: {exc}", file=sys.stderr)
        return 1

    result = SumbreakSolver().solve(board)
    if not result.solved:
        print(f"No solution: {result.error}", file=sys.stderr)
        return 1

    for step, move in enumerate(result.moves, start=1):
        (sr, sc), (tr, tc) = move.source, move.target
        print(f"{step:2}. ({sr + 1},{sc + 1}) -> ({tr + 1},{tc + 1})  = {move.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
