from __future__ import annotations

import contextlib
import io
import itertools
import sys
from pathlib import Path
from typing import Protocol, TypedDict

try:
    from .common import JsonDict, activate_game_import_context, attach_captured_logs, game_root_for_worker, run_worker_cli
except ImportError:
    from common import JsonDict, activate_game_import_context, attach_captured_logs, game_root_for_worker, run_worker_cli


class _PatchesClueCandidate(TypedDict):
    value: int
    confidence: float


class _ParsedPatchesClue(TypedDict):
    row: int
    col: int
    shape: str
    value: int | None
    confidence: float
    candidates: list[_PatchesClueCandidate]
    badge_ratio: float
    badge_fill: float


_RecoveredClueChange = TypedDict(
    "_RecoveredClueChange",
    {
        "row": int,
        "col": int,
        "from": int | None,
        "to": int | None,
        "confidence": float,
        "candidate_rank": int,
    },
)


class _GridLinesPayload(TypedDict):
    rows: list[int]
    cols: list[int]


class _BoardBBoxPayload(TypedDict):
    x: int
    y: int
    width: int
    height: int


class _ParsedPatchesBoard(TypedDict):
    board_size: int
    clues: list[_ParsedPatchesClue]
    clue_grid: list[list[int | None]]
    board_bbox: _BoardBBoxPayload
    grid_lines: _GridLinesPayload


class _RegionLike(Protocol):
    top: int
    left: int
    height: int
    width: int
    area: int
    clue_row: int
    clue_col: int


class _SolveResultLike(Protocol):
    solved: bool
    regions: list[_RegionLike] | None
    iterations: int
    error: str | None
    relaxed_square_clues: int


class _SolverLike(Protocol):
    def solve(self, board_size: int, clues: list[object]) -> _SolveResultLike: ...


class _ParserLike(Protocol):
    def __init__(self, board_size: int) -> None: ...

    def parse_image(self, image_path: str) -> _ParsedPatchesBoard: ...


class _AttemptPayload(TypedDict):
    parsed: _ParsedPatchesBoard
    solve_result: _SolveResultLike
    recovered_clues: list[_RecoveredClueChange]
    recovery_attempts: int
    score: float
    board_size: int


def _build_solution_grid(board_size: int, regions: list[dict[str, int]]) -> list[list[int]]:
    grid = [[0 for _ in range(board_size)] for _ in range(board_size)]
    for index, region in enumerate(regions, start=1):
        top = int(region["top"])
        left = int(region["left"])
        height = int(region["height"])
        width = int(region["width"])
        for row in range(top, top + height):
            for col in range(left, left + width):
                grid[row][col] = int(index)
    return grid


def _build_solver_clues(parsed_clues: list[_ParsedPatchesClue], value_overrides: dict[int, int | None] | None = None) -> list[object]:
    from src.patches_solver import PatchesClue

    overrides = value_overrides or {}
    clues = []
    for index, clue in enumerate(parsed_clues):
        override_value = overrides.get(index, clue.get("value"))
        clues.append(
            PatchesClue(
                row=int(clue["row"]),
                col=int(clue["col"]),
                shape=str(clue.get("shape") or "any"),
                area=(int(override_value) if override_value is not None else None),
            )
        )
    return clues


def _build_value_options(clue: _ParsedPatchesClue, board_size: int) -> list[tuple[int | None, float, int]]:
    max_value = board_size * board_size
    options: list[tuple[int | None, float, int]] = []
    seen: set[int | None] = set()

    primary_value = clue.get("value")
    if primary_value is None:
        options.append((None, 1.0, 0))
        seen.add(None)
    else:
        value = int(primary_value)
        primary_confidence = float(clue.get("confidence") or 1.0)
        options.append((value, primary_confidence, 0))
        seen.add(value)

    for rank, candidate in enumerate(clue.get("candidates") or [], start=1):
        value = int(candidate.get("value") or 0)
        if value <= 0 or value > max_value or value in seen:
            continue
        seen.add(value)
        options.append((value, float(candidate.get("confidence") or 0.0), rank))
        if len(options) >= 4:
            break

    return options


def _recover_with_ocr_candidates(
    solver: _SolverLike,
    parsed_clues: list[_ParsedPatchesClue],
    board_size: int,
    base_result: _SolveResultLike,
) -> tuple[_SolveResultLike, list[_RecoveredClueChange], int]:
    option_lists = [_build_value_options(clue, board_size) for clue in parsed_clues]
    combination_count = 1
    for options in option_lists:
        combination_count *= max(1, len(options))

    if combination_count <= 1:
        return base_result, [], 0

    max_candidate_assignments = 12000
    candidate_assignments: list[tuple[float, tuple[tuple[int | None, float, int], ...]]] = []
    for assignment_index, assignment in enumerate(itertools.product(*option_lists)):
        if assignment_index >= max_candidate_assignments:
            break
        score = 0.0
        for value, confidence, rank in assignment:
            del value
            score += float(confidence) - (float(rank) * 0.06)
        candidate_assignments.append((score, assignment))

    candidate_assignments.sort(key=lambda item: item[0], reverse=True)

    base_values = [clue.get("value") for clue in parsed_clues]
    attempted = 0

    for _score, assignment in candidate_assignments:
        values = [value for value, _confidence, _rank in assignment]
        if values == base_values:
            continue

        overrides = {index: values[index] for index in range(len(values))}
        solve_result = solver.solve(
            board_size=int(board_size),
            clues=_build_solver_clues(parsed_clues, value_overrides=overrides),
        )
        attempted += 1

        if not solve_result.solved:
            continue

        replaced: list[_RecoveredClueChange] = []
        for index, selected in enumerate(assignment):
            selected_value, selected_confidence, selected_rank = selected
            original = parsed_clues[index].get("value")
            if selected_value == original:
                continue

            replaced.append(
                {
                    "row": int(parsed_clues[index]["row"]),
                    "col": int(parsed_clues[index]["col"]),
                    "from": None if original is None else int(original),
                    "to": None if selected_value is None else int(selected_value),
                    "confidence": float(selected_confidence),
                    "candidate_rank": int(selected_rank),
                }
            )

        if base_result.solved and solve_result.relaxed_square_clues > base_result.relaxed_square_clues:
            continue

        return solve_result, replaced, attempted

    return base_result, [], attempted


def _has_ocr_alternatives(parsed_clues: list[_ParsedPatchesClue], board_size: int) -> bool:
    for clue in parsed_clues:
        if len(_build_value_options(clue, board_size)) > 1:
            return True
    return False


def _should_try_ocr_recovery(attempt: _AttemptPayload) -> bool:
    solve_result = attempt["solve_result"]
    parsed = attempt["parsed"]
    board_size = int(attempt["board_size"])
    if not _has_ocr_alternatives(parsed["clues"], board_size):
        return False

    if not _is_confident_patches_attempt(attempt):
        return True

    if int(solve_result.relaxed_square_clues) > 0:
        return True

    return any(
        clue.get("value") is not None and float(clue.get("confidence") or 0.0) < 0.92
        for clue in parsed["clues"]
    )


def _attempt_solve_for_board_size(
    image_path: Path,
    board_size: int,
    parser_cls: type[_ParserLike],
    solver_cls: type[_SolverLike],
    *,
    allow_recovery: bool = True,
) -> _AttemptPayload:
    parser = parser_cls(board_size=board_size)
    parsed = parser.parse_image(str(image_path))

    solver = solver_cls()
    clues = _build_solver_clues(parsed["clues"])
    solve_result = solver.solve(board_size=int(parsed["board_size"]), clues=clues)

    recovered_clues: list[_RecoveredClueChange] = []
    recovery_attempts = 0
    base_attempt = {
        "parsed": parsed,
        "solve_result": solve_result,
        "recovered_clues": recovered_clues,
        "recovery_attempts": recovery_attempts,
        "score": 0.0,
        "board_size": int(parsed["board_size"]),
    }

    if allow_recovery and _should_try_ocr_recovery(base_attempt):
        solve_result, recovered_clues, recovery_attempts = _recover_with_ocr_candidates(
            solver=solver,
            parsed_clues=parsed["clues"],
            board_size=int(parsed["board_size"]),
            base_result=solve_result,
        )

    clue_count = int(len(parsed["clues"]))
    numbered_clue_count = int(sum(1 for clue in parsed["clues"] if clue.get("value") is not None))
    unknown_clue_count = clue_count - numbered_clue_count
    confidence_total = float(sum(float(clue.get("confidence") or 0.0) for clue in parsed["clues"]))

    score = (
        (6000.0 if solve_result.solved else 0.0)
        + (numbered_clue_count * 18.0)
        - (unknown_clue_count * 12.0)
        + (confidence_total * 14.0)
        - (float(len(recovered_clues)) * 8.0)
        - (float(solve_result.relaxed_square_clues) * 3.5)
    )

    return {
        "parsed": parsed,
        "solve_result": solve_result,
        "recovered_clues": recovered_clues,
        "recovery_attempts": int(recovery_attempts),
        "score": float(score),
        "board_size": int(parsed["board_size"]),
    }


def _is_confident_patches_attempt(attempt: _AttemptPayload) -> bool:
    solve_result = attempt["solve_result"]
    parsed = attempt["parsed"]
    board_size = int(attempt["board_size"])
    clue_count = int(len(parsed["clues"]))
    numbered_clue_count = int(sum(1 for clue in parsed["clues"] if clue.get("value") is not None))
    min_numbered_clues = max(3, board_size - 3)
    return bool(
        solve_result.solved
        and 5 <= board_size <= 9
        and clue_count >= max(4, board_size)
        and numbered_clue_count >= min_numbered_clues
    )


def _base_attempt_recovery_priority(attempt: _AttemptPayload) -> tuple[int, float, int]:
    parsed = attempt["parsed"]
    clue_count = int(len(parsed["clues"]))
    numbered_clue_count = int(sum(1 for clue in parsed["clues"] if clue.get("value") is not None))
    return (
        0 if clue_count >= max(4, int(attempt["board_size"])) else 1,
        -float(numbered_clue_count),
        abs(int(attempt["board_size"]) - 6),
    )


def solve(image_path: Path) -> JsonDict:
    game_root = game_root_for_worker(__file__, "patches_solver")
    if not game_root.exists():
        return {
            "puzzle": "patches",
            "solved": False,
            "error": "Patches project folder not found.",
        }

    activate_game_import_context(game_root)

    from src.image_parser import PatchesImageParser
    from src.patches_solver import PatchesSolver

    captured_logs = io.StringIO()

    with contextlib.redirect_stdout(captured_logs), contextlib.redirect_stderr(captured_logs):
        attempts: list[_AttemptPayload] = []
        for candidate_size in (6, 7, 8, 9):
            try:
                attempt = _attempt_solve_for_board_size(
                    image_path=image_path,
                    board_size=int(candidate_size),
                    parser_cls=PatchesImageParser,
                    solver_cls=PatchesSolver,
                    allow_recovery=False,
                )
            except Exception:
                continue
            attempts.append(attempt)
            if _is_confident_patches_attempt(attempt) and not _should_try_ocr_recovery(attempt):
                break

        if attempts and (
            not any(_is_confident_patches_attempt(attempt) for attempt in attempts)
            or any(_should_try_ocr_recovery(attempt) for attempt in attempts)
        ):
            recovery_sizes = [
                int(attempt["board_size"])
                for attempt in sorted(attempts, key=_base_attempt_recovery_priority)[:2]
            ]
            for candidate_size in recovery_sizes:
                try:
                    recovery_attempt = _attempt_solve_for_board_size(
                        image_path=image_path,
                        board_size=int(candidate_size),
                        parser_cls=PatchesImageParser,
                        solver_cls=PatchesSolver,
                        allow_recovery=True,
                    )
                except Exception:
                    continue
                attempts.append(recovery_attempt)
                if _is_confident_patches_attempt(recovery_attempt):
                    break

    if not attempts:
        return {
            "puzzle": "patches",
            "solved": False,
            "error": "Could not parse board clues from screenshot.",
        }

    attempts.sort(key=lambda attempt: attempt["score"], reverse=True)
    best_attempt = attempts[0]

    parsed = best_attempt["parsed"]
    solve_result = best_attempt["solve_result"]
    recovered_clues = best_attempt["recovered_clues"]
    recovery_attempts = int(best_attempt["recovery_attempts"])

    regions_payload: list[dict[str, int]] = []
    if solve_result.regions is not None:
        for region in solve_result.regions:
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

    board_size = int(parsed["board_size"])
    solution_grid = _build_solution_grid(board_size, regions_payload) if solve_result.solved else None
    clue_count = int(len(parsed["clues"]))
    numbered_clue_count = int(sum(1 for clue in parsed["clues"] if clue.get("value") is not None))
    min_numbered_clues = max(3, board_size - 3)
    parse_reliable = bool(
        solve_result.solved
        and clue_count >= max(4, board_size)
        and numbered_clue_count >= min_numbered_clues
        and parsed.get("board_bbox") is not None
    )

    solved_payload = bool(solve_result.solved and parse_reliable)
    if not solved_payload:
        regions_payload = []
        solution_grid = None

    response = {
        "puzzle": "patches",
        "solved": solved_payload,
        "board_size": board_size,
        "regions": regions_payload,
        "moves": regions_payload,
        "solution_grid": solution_grid,
        "clues": parsed["clues"],
        "clue_grid": parsed["clue_grid"],
        "error": None if solved_payload else (solve_result.error or "Detected Patches board/OCR is not reliable enough to apply a solution."),
        "details": {
            "iterations": int(solve_result.iterations),
            "clue_count": clue_count,
            "numbered_clue_count": numbered_clue_count,
            "min_numbered_clues": min_numbered_clues,
            "raw_solver_solved": bool(solve_result.solved),
            "relaxed_square_clues": int(solve_result.relaxed_square_clues),
            "parse_reliable": parse_reliable,
            "ocr_recovery_applied": bool(recovered_clues),
            "ocr_recovery_attempts": int(recovery_attempts),
            "recovered_clues": recovered_clues,
            "size_search_candidates": [int(attempt["board_size"]) for attempt in attempts],
            "selected_board_size": int(best_attempt["board_size"]),
            "board_bbox": parsed.get("board_bbox"),
        },
    }

    attach_captured_logs(response, captured_logs)

    return response


def main() -> int:
    return run_worker_cli(
        argv=sys.argv,
        solve_fn=solve,
        worker_script="solve_patches_worker.py",
        worker_label="Patches",
    )


if __name__ == "__main__":
    raise SystemExit(main())
