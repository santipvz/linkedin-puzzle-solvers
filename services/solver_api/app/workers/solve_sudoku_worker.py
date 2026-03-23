from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _normalize_board(board: list[list[Any]] | None) -> list[list[int]] | None:
    if board is None:
        return None
    return [[int(value) for value in row] for row in board]


def solve(image_path: Path) -> dict[str, Any]:
    game_root = _repo_root() / "games" / "sudoku_solver"
    if not game_root.exists():
        return {
            "puzzle": "sudoku",
            "solved": False,
            "error": "Mini Sudoku project folder not found.",
        }

    sys.path.insert(0, str(game_root))

    from src.image_parser import MiniSudokuImageParser
    from src.mini_sudoku_solver import MiniSudokuSolver

    parser = MiniSudokuImageParser()
    solver = MiniSudokuSolver()
    captured_logs = io.StringIO()

    with contextlib.redirect_stdout(captured_logs), contextlib.redirect_stderr(captured_logs):
        parsed = parser.parse_image(str(image_path))

    initial_board = parsed["board"]
    solve_result = solver.solve(initial_board)

    fixed_cells_payload: list[dict[str, Any]] = []
    for cell in parsed["fixed_cells"]:
        fixed_cells_payload.append(
            {
                "row": int(cell["row"]),
                "col": int(cell["col"]),
                "value": int(cell["value"]),
                "confidence": float(cell["confidence"]),
                "overlay_ratio": float(cell.get("overlay_ratio") or 0.0),
                "candidates": [
                    {
                        "value": int(candidate["value"]),
                        "confidence": float(candidate["confidence"]),
                    }
                    for candidate in cell.get("candidates", [])
                ],
            }
        )

    moves: list[dict[str, int]] = []
    if solve_result.solved and solve_result.board is not None:
        for row in range(len(initial_board)):
            for col in range(len(initial_board[row])):
                if int(initial_board[row][col]) != 0:
                    continue
                moves.append(
                    {
                        "row": int(row),
                        "col": int(col),
                        "value": int(solve_result.board[row][col]),
                    }
                )

    solution_grid = _normalize_board(solve_result.board)
    ocr_stats = parsed.get("ocr") or {}
    overlay_cell_count = int(ocr_stats.get("overlay_cell_count") or 0)
    error_message = None if solve_result.solved else solve_result.error

    if not solve_result.solved and overlay_cell_count >= 3:
        error_message = (
            "Detected existing solve-overlay markers in the screenshot. "
            "Clear overlay and solve again."
        )

    response = {
        "puzzle": "sudoku",
        "solved": bool(solve_result.solved),
        "board_size": 6,
        "moves": moves,
        "solution_grid": solution_grid,
        "initial_grid": _normalize_board(initial_board),
        "fixed_cells": fixed_cells_payload,
        "error": error_message,
        "details": {
            "iterations": int(solve_result.iterations),
            "fixed_count": int(ocr_stats.get("fixed_count") or len(fixed_cells_payload)),
            "avg_confidence": float(ocr_stats.get("avg_confidence") or 0.0),
            "min_confidence": float(ocr_stats.get("min_confidence") or 0.0),
            "uncertain_count": int(ocr_stats.get("uncertain_count") or 0),
            "overlay_cell_count": overlay_cell_count,
            "board_bbox": parsed.get("board_bbox"),
        },
    }

    logs_value = captured_logs.getvalue().strip()
    if logs_value:
        response["logs"] = logs_value[:1200]

    return response


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: solve_sudoku_worker.py <image_path>", file=sys.stderr)
        return 1

    image_path = Path(sys.argv[1]).resolve()
    if not image_path.exists():
        print(f"Image file not found: {image_path}", file=sys.stderr)
        return 1

    try:
        result = solve(image_path)
    except Exception as exc:
        print(f"Mini Sudoku worker crashed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
