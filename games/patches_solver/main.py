#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.image_parser import PatchesImageParser
from src.patches_solver import PatchesClue, PatchesSolver


def solve_image(image_path: str) -> dict[str, object]:
    parser = PatchesImageParser()
    parsed = parser.parse_image(image_path)

    clues = [
        PatchesClue(
            row=int(clue["row"]),
            col=int(clue["col"]),
            shape=str(clue.get("shape") or "any"),
            area=(int(clue["value"]) if clue.get("value") is not None else None),
        )
        for clue in parsed["clues"]
    ]

    solver = PatchesSolver()
    solved = solver.solve(board_size=int(parsed["board_size"]), clues=clues)

    regions_payload = []
    if solved.regions:
        for region in solved.regions:
            regions_payload.append(
                {
                    "top": int(region.top),
                    "left": int(region.left),
                    "height": int(region.height),
                    "width": int(region.width),
                    "area": int(region.area),
                    "clue_row": int(region.clue_row),
                    "clue_col": int(region.clue_col),
                }
            )

    return {
        "puzzle": "patches",
        "solved": bool(solved.solved),
        "board_size": int(parsed["board_size"]),
        "clues": parsed["clues"],
        "regions": regions_payload,
        "error": solved.error,
        "details": {
            "iterations": int(solved.iterations),
            "clue_count": int(len(parsed["clues"])),
            "numbered_clue_count": int(sum(1 for clue in parsed["clues"] if clue.get("value") is not None)),
            "relaxed_square_clues": int(solved.relaxed_square_clues),
            "board_bbox": parsed.get("board_bbox"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve LinkedIn Patches from a screenshot")
    parser.add_argument("image", help="Path to image")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}", file=sys.stderr)
        return 1

    try:
        result = solve_image(args.image)
    except Exception as exc:
        print(f"Patches solver failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Solved: {result['solved']}")
    print(f"Board size: {result['board_size']}")
    if result["regions"]:
        for region in result["regions"]:
            print(
                f"- clue=({region['clue_row']},{region['clue_col']}) "
                f"rect=({region['top']},{region['left']}) {region['height']}x{region['width']} area={region['area']}"
            )
    if result["error"]:
        print(f"Error: {result['error']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
