from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from .common import JsonDict, ensure_sys_path, repo_root_for_worker, run_worker_cli
except ImportError:
    from common import JsonDict, ensure_sys_path, repo_root_for_worker, run_worker_cli


REPO_ROOT = repo_root_for_worker(__file__)
ensure_sys_path(REPO_ROOT)

from games.sumbreak_solver.src.sumbreak_solver import SumbreakSolver
from services.solver_api.app.domain.sumbreak_board import validate_sumbreak_board


PIPELINE_REVISION = 1


def _failure(error: str, board_size: int = 0, **details: object) -> JsonDict:
    return {
        "puzzle": "sumbreak",
        "solved": False,
        "board_size": board_size,
        "error": error,
        "details": {"parse_reliable": False, "pipeline_revision": PIPELINE_REVISION, **details},
        "moves": [],
    }


def solve(image_path: str | Path, *, parsed_board: JsonDict | None = None) -> JsonDict:
    del image_path  # Tile values come from the page; the image is only kept for captures.
    if parsed_board is None:
        return _failure("Sumbreak reads tile values from the LinkedIn page. Solve it from the game page with the extension.")
    try:
        board = validate_sumbreak_board(parsed_board)["board"]
    except Exception as exc:
        return _failure(f"Invalid Sumbreak board: {exc}")

    rows, columns = len(board), len(board[0])
    result = SumbreakSolver().solve(board)
    details: JsonDict = {
        "parse_reliable": True,
        "pipeline_revision": PIPELINE_REVISION,
        "input_source": "page",
        "rows": rows,
        "columns": columns,
        "board": board,
        "tile_count": sum(value is not None for row in board for value in row),
        "search_nodes": result.nodes,
    }
    if not result.solved:
        response = _failure(result.error or "No Sumbreak solution found.", max(rows, columns), **details)
        response["details"]["parse_reliable"] = True
        return response

    details["steps"] = len(result.moves)
    details["final_cell"] = None if result.final_cell is None else {"row": result.final_cell[0], "col": result.final_cell[1]}
    details["final_value"] = result.final_value
    return {
        "puzzle": "sumbreak",
        "solved": True,
        "board_size": max(rows, columns),
        "error": None,
        "details": details,
        "moves": [
            {
                "row": move.source[0],
                "col": move.source[1],
                "to_row": move.target[0],
                "to_col": move.target[1],
                "value": move.value,
            }
            for move in result.moves
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2] == "--parsed-board":
        page_board = json.load(sys.stdin)
        raise SystemExit(run_worker_cli(sys.argv[:2], lambda path: solve(path, parsed_board=page_board), Path(__file__).name, "Sumbreak"))
    raise SystemExit(run_worker_cli(sys.argv, solve, Path(__file__).name, "Sumbreak"))
