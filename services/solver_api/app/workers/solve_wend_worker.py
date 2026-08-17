from __future__ import annotations

import contextlib
from functools import lru_cache
import io
import sys
from pathlib import Path

try:
    from .common import JsonDict, attach_captured_logs, ensure_sys_path, repo_root_for_worker, run_worker_cli
except ImportError:
    from common import JsonDict, attach_captured_logs, ensure_sys_path, repo_root_for_worker, run_worker_cli


REPO_ROOT = repo_root_for_worker(__file__)
ensure_sys_path(REPO_ROOT)

from games.wend_solver.src.dictionary import load_wend_dictionary
from games.wend_solver.src.image_parser import WendImageParser
from games.wend_solver.src.wend_solver import WendSolver


OCR_ALTERNATE_SCORE_DELTA = 0.14
MIN_OCR_CELL_CONFIDENCE = 0.35
MIN_OCR_AVG_CONFIDENCE = 0.72
PIPELINE_REVISION = 2


@lru_cache(maxsize=1)
def _get_solver() -> WendSolver:
    return WendSolver(load_wend_dictionary())


def _ocr_letter_options(parsed: JsonDict) -> dict[tuple[int, int], list[tuple[str, float]]]:
    details = parsed.get("ocr") if isinstance(parsed.get("ocr"), dict) else {}
    cells = details.get("cells") if isinstance(details.get("cells"), list) else []
    options: dict[tuple[int, int], list[tuple[str, float]]] = {}

    for cell in cells:
        if not isinstance(cell, dict):
            continue
        try:
            row = int(cell.get("row"))
            col = int(cell.get("col"))
            best_score = float(cell.get("confidence") or 0.0)
        except (TypeError, ValueError):
            continue

        candidates = cell.get("candidates") if isinstance(cell.get("candidates"), list) else []
        letters: list[tuple[str, float]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            letter = str(candidate.get("letter") or "").strip().upper()
            try:
                confidence = float(candidate.get("confidence") or 0.0)
            except (TypeError, ValueError):
                continue
            if len(letter) != 1 or not letter.isalpha():
                continue
            if confidence < best_score - OCR_ALTERNATE_SCORE_DELTA:
                continue
            if all(existing_letter != letter for existing_letter, _ in letters):
                letters.append((letter, max(0.0, best_score - confidence)))

        if letters:
            options[(row, col)] = letters

    return options


def solve(image_path: str | Path) -> JsonDict:
    captured_logs = io.StringIO()
    with contextlib.redirect_stdout(captured_logs):
        try:
            parsed = WendImageParser().parse_image(image_path)
        except Exception as exc:
            response: JsonDict = {
                "puzzle": "wend",
                "solved": False,
                "board_size": 0,
                "error": f"Could not parse Wend image: {exc}",
                "details": {
                    "parse_reliable": False,
                    "solution_count": 0,
                },
                "words": [],
            }
            attach_captured_logs(response, captured_logs)
            return response

        board = parsed.get("board")
        lengths = parsed.get("lengths")
        board_size = int(parsed.get("board_size") or 0)
        visible_cells = int(parsed.get("visible_cells") or 0)
        if not isinstance(board, list) or not isinstance(lengths, list) or not lengths:
            response = {
                "puzzle": "wend",
                "solved": False,
                "board_size": board_size,
                "error": "Could not detect Wend word lengths. Select/capture the board plus the answer slots below it.",
                "details": {
                    "parse_reliable": False,
                    "solution_count": 0,
                    "visible_cells": visible_cells,
                    "lengths": lengths if isinstance(lengths, list) else [],
                    "board_bbox": parsed.get("board_bbox"),
                    "ocr": parsed.get("ocr"),
                },
                "words": [],
            }
            attach_captured_logs(response, captured_logs)
            return response

        solver = _get_solver()
        typed_board = board
        typed_lengths = [int(length) for length in lengths]
        letter_options = _ocr_letter_options(parsed)
        solve_result = solver.solve(
            typed_board,
            typed_lengths,
            letter_options=letter_options,
            max_solutions=10,
        )
        solutions = solve_result.solutions
        solved_board = [list(row) for row in typed_board]
        ocr_corrections: list[JsonDict] = []

        ocr_details = parsed.get("ocr") if isinstance(parsed.get("ocr"), dict) else {}
        ocr_cells = ocr_details.get("cells") if isinstance(ocr_details.get("cells"), list) else []
        min_ocr_confidence = float(ocr_details.get("min_confidence") or 0.0)
        avg_ocr_confidence = float(ocr_details.get("avg_confidence") or 0.0)
        parse_reliable = (
            5 <= board_size <= 8
            and len(typed_board) == board_size
            and all(isinstance(row, list) and len(row) == board_size for row in typed_board)
            and visible_cells == sum(typed_lengths)
            and len(ocr_cells) == visible_cells
            and all(value != "?" for row in typed_board for value in row if value is not None)
            and min_ocr_confidence >= MIN_OCR_CELL_CONFIDENCE
            and avg_ocr_confidence >= MIN_OCR_AVG_CONFIDENCE
        )
        unique_solution = solve_result.solution_count_is_exact and len(solutions) == 1
        solved = bool(parse_reliable and unique_solution)
        words_payload = []
        if solved:
            for candidate in solutions[0].words:
                for letter, (row, col) in zip(candidate.word, candidate.path):
                    original = solved_board[row][col]
                    if original != letter:
                        ocr_corrections.append({"row": row, "col": col, "from": original, "to": letter})
                        solved_board[row][col] = letter
                words_payload.append(
                    {
                        "word": candidate.word,
                        "path": [
                            {"row": int(row), "col": int(col)}
                            for row, col in candidate.path
                        ],
                    }
                )

        response = {
            "puzzle": "wend",
            "solved": solved,
            "board_size": board_size,
            "error": (
                None
                if solved
                else (
                    "Parsed Wend cell count does not match the detected word lengths."
                    if visible_cells != sum(typed_lengths)
                    else (
                        "Detected Wend board/OCR is not reliable enough to apply a solution."
                        if solutions and not parse_reliable
                        else (
                            "Wend parse produced multiple plausible solutions; refusing to auto-apply an ambiguous board."
                            if len(solutions) > 1 or not solve_result.solution_count_is_exact
                            else "No Wend solution found for the parsed letters and detected lengths."
                        )
                    )
                )
            ),
            "details": {
                "parse_reliable": parse_reliable,
                "solution_count": len(solutions),
                "solution_count_is_exact": solve_result.solution_count_is_exact,
                "solution_limit": solve_result.solution_limit,
                "unique_solution": unique_solution,
                "pipeline_revision": PIPELINE_REVISION,
                "solution_costs": [
                    float(sum(candidate.ocr_cost for candidate in solution.words))
                    for solution in solutions
                ],
                "visible_cells": visible_cells,
                "lengths": [int(length) for length in lengths],
                "board": solved_board,
                "parsed_board": board,
                "ocr_corrections": ocr_corrections,
                "search_mode": "weighted_ocr_exact_cover",
                "board_bbox": parsed.get("board_bbox"),
                "ocr": parsed.get("ocr"),
            },
            "words": words_payload,
        }
        attach_captured_logs(response, captured_logs)
        return response

    response = {
        "puzzle": "wend",
        "solved": False,
        "board_size": 0,
        "error": "Wend image parser returned no parsed board.",
        "details": {"parse_reliable": False, "solution_count": 0},
        "words": [],
    }
    attach_captured_logs(response, captured_logs)
    return response


if __name__ == "__main__":
    raise SystemExit(run_worker_cli(sys.argv, solve, Path(__file__).name, "Wend"))
