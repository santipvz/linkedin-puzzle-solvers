#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.image_parser import ZipImageParser
from src.zip_solver import ZipSolver


def solve_image(image_path: str) -> dict[str, object]:
    parser = ZipImageParser()
    parsed = parser.parse_image(image_path)

    clues = {(entry["row"], entry["col"]): entry["value"] for entry in parsed["clues"]}

    solver = ZipSolver()
    solved = solver.solve(
        size=int(parsed["size"]),
        blocked_h=parsed["blocked_h"],
        blocked_v=parsed["blocked_v"],
        clues=clues,
    )

    return {
        "size": int(parsed["size"]),
        "clues": parsed["clues"],
        "clue_grid": parsed["clue_grid"],
        "board_bbox": parsed["board_bbox"],
        "iterations": solved.iterations,
        "solved": solved.solved,
        "error": solved.error,
        "path": solved.path,
        "directions": solved.directions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve LinkedIn Zip from a screenshot")
    parser.add_argument("image", help="Path to image")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}", file=sys.stderr)
        return 1

    try:
        result = solve_image(args.image)
    except Exception as exc:
        print(f"Zip solver failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print("Detected clues:")
    for entry in result["clues"]:
        print(
            f"  value={entry['value']} at row={entry['row']} col={entry['col']}"
            f" (score={entry['confidence']:.3f})"
        )

    if result["solved"] and result["path"] is not None:
        print(f"\nSolved with {len(result['path'])} cells and {result['iterations']} iterations.")
    else:
        print(f"\nNo solution found: {result['error']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
