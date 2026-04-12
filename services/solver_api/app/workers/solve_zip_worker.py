from __future__ import annotations

import contextlib
import io
import itertools
import sys
from pathlib import Path
from typing import Any

try:
    from .common import ensure_sys_path, game_root_for_worker, run_worker_cli
except ImportError:
    from common import ensure_sys_path, game_root_for_worker, run_worker_cli


def _build_primary_clues(clue_entries: list[dict[str, Any]]) -> dict[tuple[int, int], int]:
    return {
        (int(entry["row"]), int(entry["col"])): int(entry["value"])
        for entry in clue_entries
    }


def _score_clue_assignment(values: list[int], confidences: list[float], rank_penalty: float) -> float:
    score = float(sum(confidences)) - rank_penalty

    if 1 in values:
        score += 0.6
    else:
        score -= 2.0

    sorted_values = sorted(values)
    expected = list(range(sorted_values[0], sorted_values[0] + len(sorted_values)))
    if sorted_values == expected:
        score += 0.45
    else:
        gap_penalty = sum(
            max(0, sorted_values[index + 1] - sorted_values[index] - 1)
            for index in range(len(sorted_values) - 1)
        )
        score -= float(gap_penalty) * 0.12

    return score


def _build_clue_options(clue_entries: list[dict[str, Any]]) -> list[list[tuple[int, float, int]]]:
    options_per_cell: list[list[tuple[int, float, int]]] = []

    for entry in clue_entries:
        candidates = entry.get("candidates") or []
        ranked: list[tuple[int, float, int]] = []
        seen: set[int] = set()

        primary_value = int(entry["value"])
        primary_confidence = float(entry.get("confidence") or 0.0)
        ranked.append((primary_value, primary_confidence, 0))
        seen.add(primary_value)

        for rank, candidate in enumerate(candidates, start=1):
            value = int(candidate.get("value") or 0)
            if value <= 0 or value in seen:
                continue
            seen.add(value)
            ranked.append((value, float(candidate.get("confidence") or 0.0), rank))
            if len(ranked) >= 4:
                break

        options_per_cell.append(ranked)

    return options_per_cell


def _best_contiguous_assignment(
    options_per_cell: list[list[tuple[int, float, int]]],
    expected_values: list[int],
) -> list[tuple[int, float, int]] | None:
    if not options_per_cell:
        return None

    expected_set = set(expected_values)
    cell_count = len(options_per_cell)

    domains: list[list[tuple[int, float, int]]] = []
    value_coverage = {value: 0 for value in expected_values}

    def option_score(option: tuple[int, float, int]) -> float:
        value, confidence, rank = option
        del value
        return float(confidence) - (float(rank) * 0.05)

    for options in options_per_cell:
        best_by_value: dict[int, tuple[int, float, int]] = {}
        for option in options:
            value = int(option[0])
            if value not in expected_set:
                continue

            current = best_by_value.get(value)
            if current is None or option_score(option) > option_score(current):
                best_by_value[value] = option

        if not best_by_value:
            return None

        domain = sorted(best_by_value.values(), key=option_score, reverse=True)
        domains.append(domain)

        for value in best_by_value:
            value_coverage[value] += 1

    if any(count == 0 for count in value_coverage.values()):
        return None

    index_order = sorted(range(cell_count), key=lambda index: len(domains[index]))
    used_values: set[int] = set()
    current_assignment: list[tuple[int, float, int] | None] = [None for _ in range(cell_count)]
    best_score = float("-inf")
    best_assignment: list[tuple[int, float, int]] | None = None

    def remaining_feasible(order_position: int) -> bool:
        remaining_values = expected_set - used_values
        if len(remaining_values) > (cell_count - order_position):
            return False

        for value in remaining_values:
            value_is_possible = False
            for next_position in range(order_position, cell_count):
                index = index_order[next_position]
                if any(candidate[0] == value for candidate in domains[index]):
                    value_is_possible = True
                    break

            if not value_is_possible:
                return False

        return True

    def dfs(order_position: int, score: float) -> None:
        nonlocal best_score, best_assignment

        if order_position == cell_count:
            if score <= best_score:
                return

            snapshot: list[tuple[int, float, int]] = []
            for item in current_assignment:
                if item is None:
                    return
                snapshot.append(item)

            best_score = score
            best_assignment = snapshot
            return

        index = index_order[order_position]
        for option in domains[index]:
            value = int(option[0])
            if value in used_values:
                continue

            current_assignment[index] = option
            used_values.add(value)

            if remaining_feasible(order_position + 1):
                dfs(order_position + 1, score + option_score(option))

            used_values.remove(value)
            current_assignment[index] = None

    dfs(order_position=0, score=0.0)
    return best_assignment


def _build_recovered_payload(
    clue_entries: list[dict[str, Any]],
    assignment: list[tuple[int, float, int]],
) -> tuple[dict[tuple[int, int], int], list[dict[str, Any]]]:
    clues: dict[tuple[int, int], int] = {}
    replaced: list[dict[str, Any]] = []

    for index, (value, confidence, rank) in enumerate(assignment):
        entry = clue_entries[index]
        row = int(entry["row"])
        col = int(entry["col"])
        clues[(row, col)] = int(value)

        original_value = int(entry["value"])
        if value == original_value:
            continue

        replaced.append(
            {
                "row": row,
                "col": col,
                "from": original_value,
                "to": int(value),
                "confidence": float(confidence),
                "candidate_rank": int(rank),
            }
        )

    return clues, replaced


def _recover_duplicate_clues(
    clue_entries: list[dict[str, Any]],
    board_size: int,
    blocked_h: list[list[bool]],
    blocked_v: list[list[bool]],
) -> tuple[dict[tuple[int, int], int], list[dict[str, Any]]]:
    primary = _build_primary_clues(clue_entries)
    if not clue_entries:
        return primary, []

    primary_values = [int(entry["value"]) for entry in clue_entries]
    has_duplicate = len(set(primary_values)) != len(primary_values)
    expected_values = list(range(1, len(clue_entries) + 1))
    is_contiguous = sorted(primary_values) == expected_values

    if not has_duplicate and is_contiguous:
        return primary, []

    options_per_cell = _build_clue_options(clue_entries)

    solver = None
    best_payload: tuple[float, dict[tuple[int, int], int], list[dict[str, Any]]] | None = None

    def consider_assignment(assignment: list[tuple[int, float, int]]) -> None:
        nonlocal solver, best_payload

        values = [int(value) for value, _, _ in assignment]
        if len(set(values)) != len(values):
            return
        if 1 not in values:
            return

        clues, replaced = _build_recovered_payload(clue_entries, assignment)
        confidences = [float(confidence) for _, confidence, _ in assignment]
        rank_penalty = float(sum(rank for _, _, rank in assignment)) * 0.05
        score = _score_clue_assignment(values, confidences, rank_penalty)

        if sorted(values) == expected_values:
            score += 0.25

        if solver is None:
            from src.zip_solver import ZipSolver

            solver = ZipSolver()

        solve_result = solver.solve(size=board_size, blocked_h=blocked_h, blocked_v=blocked_v, clues=clues)
        if not solve_result.solved:
            return

        if best_payload is None or score > best_payload[0]:
            best_payload = (score, clues, replaced)

    if not is_contiguous:
        contiguous_assignment = _best_contiguous_assignment(
            options_per_cell=options_per_cell,
            expected_values=expected_values,
        )
        if contiguous_assignment is not None:
            consider_assignment(contiguous_assignment)

    if has_duplicate:
        for combo in itertools.product(*options_per_cell):
            consider_assignment(list(combo))

    if best_payload is None:
        return primary, []

    return best_payload[1], best_payload[2]


def solve(image_path: Path) -> dict[str, Any]:
    game_root = game_root_for_worker(__file__, "zip_solver")
    if not game_root.exists():
        return {
            "puzzle": "zip",
            "solved": False,
            "error": "Zip project folder not found.",
        }

    ensure_sys_path(game_root)

    from src.image_parser import ZipImageParser
    from src.zip_solver import ZipSolver

    parser = ZipImageParser()
    solver = ZipSolver()
    captured_logs = io.StringIO()

    with contextlib.redirect_stdout(captured_logs), contextlib.redirect_stderr(captured_logs):
        parsed = parser.parse_image(str(image_path))

    clues, recovered_clues = _recover_duplicate_clues(
        clue_entries=parsed["clues"],
        board_size=int(parsed["size"]),
        blocked_h=parsed["blocked_h"],
        blocked_v=parsed["blocked_v"],
    )

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
            "duplicate_recovery_applied": bool(recovered_clues),
            "recovered_clues": recovered_clues,
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
        worker_script="solve_zip_worker.py",
        worker_label="Zip",
    )


if __name__ == "__main__":
    raise SystemExit(main())
