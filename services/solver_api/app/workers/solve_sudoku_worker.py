from __future__ import annotations

import contextlib
import io
import itertools
import sys
from pathlib import Path
from typing import Any

try:
    from .common import activate_game_import_context, game_root_for_worker, run_worker_cli
except ImportError:
    from common import activate_game_import_context, game_root_for_worker, run_worker_cli


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


def _is_ambiguous_solution(result: Any) -> bool:
    if not getattr(result, "solved", False):
        return False

    solution_count = int(getattr(result, "solution_count", 1) or 1)
    return solution_count > 1


def _recover_from_conflicting_clues(
    solver: Any,
    initial_board: list[list[int]],
    fixed_cells: list[dict[str, Any]],
) -> tuple[Any, list[list[int]], list[dict[str, Any]]]:
    baseline_result = solver.solve(initial_board, max_solutions=2)
    if baseline_result.solved and not _is_ambiguous_solution(baseline_result):
        return baseline_result, initial_board, []

    should_attempt_recovery = _is_conflicting_clue_error(baseline_result.error) or _is_ambiguous_solution(baseline_result)
    if not should_attempt_recovery:
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
    max_adjustments = min(3, len(suspects))

    best_result: Any | None = None
    best_board: list[list[int]] | None = None
    best_adjustments: list[dict[str, Any]] | None = None
    best_score: tuple[float, ...] | None = None

    for adjustment_count in range(1, max_adjustments + 1):
        for combo in itertools.combinations(suspects, adjustment_count):
            option_sets: list[list[dict[str, Any]]] = []

            for cell in combo:
                current_value = int(cell.get("value") or 0)
                options: list[dict[str, Any]] = []
                seen_values: set[int] = set()

                for candidate in cell.get("candidates", []):
                    candidate_value = int(candidate.get("value") or 0)
                    candidate_confidence = float(candidate.get("confidence") or 0.0)

                    if candidate_value <= 0 or candidate_value > 6:
                        continue
                    if candidate_value == current_value:
                        continue
                    if candidate_value in seen_values:
                        continue
                    if candidate_confidence <= 0.02:
                        continue

                    seen_values.add(candidate_value)
                    options.append(
                        {
                            "replacement_value": candidate_value,
                            "replacement_confidence": candidate_confidence,
                            "source": "ocr_candidate",
                        }
                    )

                options.sort(key=lambda option: float(option["replacement_confidence"]), reverse=True)
                options = options[:3]
                options.append(
                    {
                        "replacement_value": 0,
                        "replacement_confidence": 0.0,
                        "source": "removed",
                    }
                )

                option_sets.append(options)

            for options_combo in itertools.product(*option_sets):
                candidate_board = _clone_board(initial_board)
                adjustments: list[dict[str, Any]] = []
                valid_combo = True

                for cell, option in zip(combo, options_combo):
                    row = int(cell.get("row") or 0)
                    col = int(cell.get("col") or 0)
                    value = int(cell.get("value") or 0)

                    if row < 0 or col < 0 or row >= len(candidate_board) or col >= len(candidate_board[row]):
                        valid_combo = False
                        break
                    if int(candidate_board[row][col]) != value:
                        valid_combo = False
                        break

                    replacement_value = int(option["replacement_value"])
                    if replacement_value == value:
                        continue

                    candidate_board[row][col] = replacement_value
                    adjustments.append(
                        {
                            "row": row,
                            "col": col,
                            "value": value,
                            "confidence": float(cell.get("confidence") or 0.0),
                            "replacement_value": replacement_value,
                            "replacement_confidence": float(option["replacement_confidence"]),
                            "source": str(option["source"]),
                        }
                    )

                if not valid_combo or not adjustments:
                    continue

                candidate_result = solver.solve(candidate_board, max_solutions=2)
                if not candidate_result.solved:
                    continue

                candidate_solution_count = int(getattr(candidate_result, "solution_count", 1) or 1)
                unique_bonus = 1.0 if candidate_solution_count == 1 else 0.0
                replacement_count = float(sum(1 for adjustment in adjustments if int(adjustment["replacement_value"]) != 0))
                removal_count = float(sum(1 for adjustment in adjustments if int(adjustment["replacement_value"]) == 0))
                confidence_sum = float(
                    sum(
                        float(adjustment["replacement_confidence"])
                        for adjustment in adjustments
                        if int(adjustment["replacement_value"]) != 0
                    )
                )

                score = (
                    unique_bonus,
                    -float(len(adjustments)),
                    replacement_count,
                    -removal_count,
                    confidence_sum,
                )

                if best_score is None or score > best_score:
                    best_score = score
                    best_result = candidate_result
                    best_board = candidate_board
                    best_adjustments = adjustments

                if unique_bonus >= 1.0 and len(adjustments) == 1 and replacement_count == 1:
                    return candidate_result, candidate_board, adjustments

    if best_result is not None and best_board is not None and best_adjustments is not None:
        return best_result, best_board, best_adjustments

    return baseline_result, initial_board, []


def solve(image_path: Path) -> dict[str, Any]:
    game_root = game_root_for_worker(__file__, "sudoku_solver")
    if not game_root.exists():
        return {
            "puzzle": "sudoku",
            "solved": False,
            "error": "Mini Sudoku project folder not found.",
        }

    activate_game_import_context(game_root)

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

    solution_count = int(getattr(solve_result, "solution_count", 1 if solve_result.solved else 0) or 0)
    unique_solution = bool(solve_result.solved and solution_count == 1)

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
    if unique_solution and solve_result.board is not None:
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

    solution_grid = _normalize_board(solve_result.board) if unique_solution else None
    ocr_stats = parsed.get("ocr") or {}
    overlay_cell_count = int(ocr_stats.get("overlay_cell_count") or 0)
    error_message = None if unique_solution else solve_result.error

    if solve_result.solved and not unique_solution:
        error_message = (
            "Detected multiple valid solutions from recognized clues. "
            "The screenshot likely missed one or more fixed numbers."
        )

    if not unique_solution and overlay_cell_count >= 3:
        error_message = (
            "Detected existing solve-overlay markers in the screenshot. "
            "Clear overlay and solve again."
        )

    removed_cells = [
        {
            "row": int(cell["row"]),
            "col": int(cell["col"]),
            "value": int(cell["value"]),
            "confidence": float(cell.get("confidence") or 0.0),
        }
        for cell in recovered_cells
        if int(cell.get("replacement_value") or 0) == 0
    ]

    response = {
        "puzzle": "sudoku",
        "solved": unique_solution,
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
            "solution_count": solution_count,
            "unique_solution": unique_solution,
            "conflict_recovery_applied": bool(recovered_cells),
            "removed_conflicting_cells": removed_cells,
            "adjusted_conflicting_cells": recovered_cells,
        },
    }

    logs_value = captured_logs.getvalue().strip()
    if logs_value:
        response["logs"] = logs_value[:1200]

    return response


def main() -> int:
    return run_worker_cli(
        argv=sys.argv,
        solve_fn=solve,
        worker_script="solve_sudoku_worker.py",
        worker_label="Mini Sudoku",
    )


if __name__ == "__main__":
    raise SystemExit(main())
