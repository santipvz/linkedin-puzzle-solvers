from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _normalize_board(board: list[list[Any]]) -> list[list[int]]:
    normalized: list[list[int]] = []
    for row in board:
        normalized_row: list[int] = []
        for value in row:
            if value is None:
                normalized_row.append(-1)
            else:
                normalized_row.append(int(value))
        normalized.append(normalized_row)
    return normalized


def solve(image_path: Path) -> dict[str, Any]:
    game_root = _repo_root() / "games" / "tango_solver"
    if not game_root.exists():
        return {
            "puzzle": "tango",
            "solved": False,
            "error": "Tango project folder not found.",
        }

    sys.path.insert(0, str(game_root))

    from src.image_parser import TangoImageParser
    from src.tango_solver import TangoSolver

    parser = TangoImageParser()
    solver = TangoSolver()
    captured_logs = io.StringIO()

    with contextlib.redirect_stdout(captured_logs), contextlib.redirect_stderr(captured_logs):
        board_state = parser.parse_image(str(image_path))

        if not board_state:
            return {
                "puzzle": "tango",
                "solved": False,
                "board_size": 6,
                "moves": [],
                "solution_grid": None,
                "error": "Failed to parse image into board state.",
            }

        for piece in board_state["fixed_pieces"]:
            solver.add_fixed_piece(piece["row"], piece["col"], piece["piece_type"])

        for constraint in board_state["constraints"]:
            solver.add_constraint(constraint["type"], constraint["pos1"], constraint["pos2"])

        solved = solver.solve()

    fixed_pieces_payload: list[dict[str, int]] = []
    for piece in board_state["fixed_pieces"]:
        fixed_pieces_payload.append(
            {
                "row": int(piece["row"]),
                "col": int(piece["col"]),
                "piece_type": int(piece["piece_type"]),
            }
        )

    constraints_payload: list[dict[str, Any]] = []
    for constraint in board_state["constraints"]:
        constraints_payload.append(
            {
                "type": str(constraint["type"]),
                "pos1": [int(constraint["pos1"][0]), int(constraint["pos1"][1])],
                "pos2": [int(constraint["pos2"][0]), int(constraint["pos2"][1])],
            }
        )

    fixed_lookup = {(piece["row"], piece["col"]): piece["piece_type"] for piece in board_state["fixed_pieces"]}

    moves: list[dict[str, int]] = []
    if solved:
        for row_index, row_values in enumerate(solver.board):
            for col_index, value in enumerate(row_values):
                if (row_index, col_index) in fixed_lookup:
                    continue
                if value is None:
                    continue
                moves.append(
                    {
                        "row": int(row_index),
                        "col": int(col_index),
                        "value": int(value),
                    }
                )

    response = {
        "puzzle": "tango",
        "solved": bool(solved),
        "board_size": int(solver.size),
        "moves": moves,
        "solution_grid": _normalize_board(solver.board),
        "fixed_pieces": fixed_pieces_payload,
        "constraints": constraints_payload,
        "error": None if solved else "No valid solution found.",
        "details": {
            "steps": int(solver.get_steps()),
            "fixed_count": int(len(board_state["fixed_pieces"])),
            "constraint_count": int(len(board_state["constraints"])),
        },
    }

    logs_value = captured_logs.getvalue().strip()
    if logs_value:
        response["logs"] = logs_value[:1200]

    return response


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: solve_tango_worker.py <image_path>", file=sys.stderr)
        return 1

    image_path = Path(sys.argv[1]).resolve()
    if not image_path.exists():
        print(f"Image file not found: {image_path}", file=sys.stderr)
        return 1

    try:
        result = solve(image_path)
    except Exception as exc:
        print(f"Tango worker crashed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
