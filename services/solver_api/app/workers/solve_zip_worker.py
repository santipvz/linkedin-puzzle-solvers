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


def _recover_duplicate_clues(
    clue_entries: list[dict[str, Any]],
    board_size: int,
    blocked_h: list[list[bool]],
    blocked_v: list[list[bool]],
) -> tuple[dict[tuple[int, int], int], list[dict[str, Any]]]:
    primary = _build_primary_clues(clue_entries)
    primary_values = list(primary.values())
    if len(set(primary_values)) == len(primary_values):
        return primary, []

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

    solver = None
    best_payload: tuple[float, dict[tuple[int, int], int], list[dict[str, Any]]] | None = None

    for combo in itertools.product(*options_per_cell):
        values = [value for value, _, _ in combo]
        if len(set(values)) != len(values):
            continue

        confidences = [confidence for _, confidence, _ in combo]
        rank_penalty = float(sum(rank for _, _, rank in combo)) * 0.05
        score = _score_clue_assignment(values, confidences, rank_penalty)

        clues = {
            (int(clue_entries[index]["row"]), int(clue_entries[index]["col"])): int(value)
            for index, (value, _, _) in enumerate(combo)
        }

        if solver is None:
            from src.zip_solver import ZipSolver

            solver = ZipSolver()

        solve_result = solver.solve(size=board_size, blocked_h=blocked_h, blocked_v=blocked_v, clues=clues)
        if not solve_result.solved:
            continue

        replaced: list[dict[str, Any]] = []
        for index, (value, confidence, rank) in enumerate(combo):
            original = clue_entries[index]
            original_value = int(original["value"])
            if value == original_value:
                continue

            replaced.append(
                {
                    "row": int(original["row"]),
                    "col": int(original["col"]),
                    "from": original_value,
                    "to": int(value),
                    "confidence": float(confidence),
                    "candidate_rank": int(rank),
                }
            )

        if best_payload is None or score > best_payload[0]:
            best_payload = (score, clues, replaced)

    if best_payload is None:
        return primary, []

    return best_payload[1], best_payload[2]


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
