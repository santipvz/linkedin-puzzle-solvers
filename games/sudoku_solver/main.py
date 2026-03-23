#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.image_parser import MiniSudokuImageParser
from src.mini_sudoku_solver import MiniSudokuSolver


def solve_image(image_path: str) -> dict[str, object]:
    parser = MiniSudokuImageParser()
    parsed = parser.parse_image(image_path)

    initial_board = parsed["board"]
    solver = MiniSudokuSolver()
    solved = solver.solve(initial_board)

    payload: dict[str, object] = {
        "initial_board": initial_board,
        "fixed_cells": parsed["fixed_cells"],
        "ocr": parsed["ocr"],
        "iterations": solved.iterations,
        "solved": solved.solved,
        "error": solved.error,
        "solution": solved.board,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve LinkedIn Mini Sudoku from a screenshot")
    parser.add_argument("image", help="Path to image")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}", file=sys.stderr)
        return 1

    try:
        result = solve_image(args.image)
    except Exception as exc:
        print(f"Mini Sudoku solver failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print("Initial board:")
    for row in result["initial_board"]:
        print(" ".join(str(v) if v else "." for v in row))

    if result["solved"] and result["solution"] is not None:
        print("\nSolved board:")
        for row in result["solution"]:
            print(" ".join(str(v) for v in row))
        print(f"\nIterations: {result['iterations']}")
    else:
        print(f"\nNo solution found: {result['error']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
