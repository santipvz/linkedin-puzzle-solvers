from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def solve(image_path: Path) -> dict[str, Any]:
    game_root = _repo_root() / "games" / "zip_solver"
    if not game_root.exists():
        return {
            "puzzle": "zip",
            "solved": False,
            "error": "Zip project folder not found.",
        }

    sys.path.insert(0, str(game_root))

    from src.image_parser import ZipImageParser
    from src.zip_solver import ZipSolver

    parser = ZipImageParser()
    solver = ZipSolver()
    captured_logs = io.StringIO()

    with contextlib.redirect_stdout(captured_logs), contextlib.redirect_stderr(captured_logs):
        parsed = parser.parse_image(str(image_path))

    clues = {(entry["row"], entry["col"]): entry["value"] for entry in parsed["clues"]}

    solve_result = solver.solve(
        size=int(parsed["size"]),
        blocked_h=parsed["blocked_h"],
        blocked_v=parsed["blocked_v"],
        clues=clues,
    )

    path_payload: list[dict[str, int]] = []
    if solve_result.path is not None:
        path_payload = [{"row": int(row), "col": int(col)} for row, col in solve_result.path]

    directions = [str(direction) for direction in (solve_result.directions or [])]
    start_cell = path_payload[0] if path_payload else None

    response = {
        "puzzle": "zip",
        "solved": bool(solve_result.solved),
        "board_size": int(parsed["size"]),
        "path": path_payload,
        "directions": directions,
        "moves": [{"direction": direction} for direction in directions],
        "start_cell": start_cell,
        "clues": parsed["clues"],
        "clue_grid": parsed["clue_grid"],
        "error": None if solve_result.solved else solve_result.error,
        "details": {
            "iterations": int(solve_result.iterations),
            "clue_count": int(len(parsed["clues"])),
            "board_bbox": parsed["board_bbox"],
        },
    }

    logs_value = captured_logs.getvalue().strip()
    if logs_value:
        response["logs"] = logs_value[:1200]

    return response


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: solve_zip_worker.py <image_path>", file=sys.stderr)
        return 1

    image_path = Path(sys.argv[1]).resolve()
    if not image_path.exists():
        print(f"Image file not found: {image_path}", file=sys.stderr)
        return 1

    try:
        result = solve(image_path)
    except Exception as exc:
        print(f"Zip worker crashed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
