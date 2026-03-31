from __future__ import annotations

import contextlib
import io
import itertools
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


def _clone_board(board: list[list[int]]) -> list[list[int]]:
    return [list(row) for row in board]


def _is_conflicting_clue_error(error_message: str | None) -> bool:
    if not error_message:
        return False
    return error_message.startswith("Conflicting clue value")


def _recover_from_conflicting_clues(
    solver: Any,
    initial_board: list[list[int]],
    fixed_cells: list[dict[str, Any]],
) -> tuple[Any, list[list[int]], list[dict[str, Any]]]:
    baseline_result = solver.solve(initial_board)
    if baseline_result.solved or not _is_conflicting_clue_error(baseline_result.error):
        return baseline_result, initial_board, []

    ranked_cells = sorted(
        fixed_cells,
        key=lambda cell: (
            float(cell.get("confidence") or 0.0),
            int(cell.get("row") or 0),
            int(cell.get("col") or 0),
        ),
    )
    if not ranked_cells:
        return baseline_result, initial_board, []

    suspects = ranked_cells[: min(8, len(ranked_cells))]
    max_remove = min(3, len(suspects))

    for remove_count in range(1, max_remove + 1):
        for combo in itertools.combinations(suspects, remove_count):
            candidate_board = _clone_board(initial_board)
            removed_cells: list[dict[str, Any]] = []

            for cell in combo:
                row = int(cell["row"])
                col = int(cell["col"])
                value = int(cell["value"])
                if row < 0 or col < 0 or row >= len(candidate_board) or col >= len(candidate_board[row]):
                    continue
                if int(candidate_board[row][col]) != value:
                    continue

                candidate_board[row][col] = 0
                removed_cells.append(
                    {
                        "row": row,
                        "col": col,
                        "value": value,
                        "confidence": float(cell.get("confidence") or 0.0),
                    }
                )

            if not removed_cells:
                continue

            candidate_result = solver.solve(candidate_board)
            if candidate_result.solved:
                return candidate_result, candidate_board, removed_cells

    return baseline_result, initial_board, []


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
    solve_result, solve_input_board, recovered_cells = _recover_from_conflicting_clues(
        solver,
        initial_board,
        parsed["fixed_cells"],
    )

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
        for row in range(len(solve_input_board)):
            for col in range(len(solve_input_board[row])):
                if int(solve_input_board[row][col]) != 0:
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
        "solve_input_grid": _normalize_board(solve_input_board),
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
            "conflict_recovery_applied": bool(recovered_cells),
            "removed_conflicting_cells": recovered_cells,
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
