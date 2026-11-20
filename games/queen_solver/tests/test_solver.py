from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
QUEENS_ROOT = REPO_ROOT / "games" / "queen_solver"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.workers.common import activate_game_import_context

activate_game_import_context(QUEENS_ROOT)

from src.core.models import Region
from src.queens_solver import QueensSolver
from src.solver.queens_solver import BacktrackingQueensSolver


@pytest.mark.parametrize("filename", ("board1.png", "board10.png", "board16.png"))
def test_representative_image_board(filename: str) -> None:
    board_path = Path(__file__).resolve().parent / "boards" / "solvable" / filename
    assert board_path.is_file(), f"Missing tracked Queens fixture: {board_path}"

    solved = QueensSolver(verbose=False).solve_from_image(
        str(board_path),
        "",
        "",
        generate_visualizations=False,
    )

    assert solved


def test_prevalidation_allows_single_cell_column_mix() -> None:
    solver = BacktrackingQueensSolver()
    color = np.array([0, 0, 0], dtype=np.uint8)
    regions = {
        1: Region(id=1, positions=[(0, 0)], color=color, size=0),
        2: Region(id=2, positions=[(1, 0), (1, 1)], color=color, size=0),
        3: Region(id=3, positions=[(2, 2), (2, 3)], color=color, size=0),
        4: Region(id=4, positions=[(3, 2), (3, 3)], color=color, size=0),
    }

    assert solver._pre_validate_solvability(4, regions)


PAGE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "linkedin-2026-11-20.json"
# LinkedIn's own answer for the 2026-11-20 puzzle: the queen's column in each row.
OFFICIAL_2026_11_20 = [7, 3, 8, 6, 4, 1, 5, 2, 0]


def test_worker_solves_a_page_board_without_the_image() -> None:
    from services.solver_api.app.workers.solve_queens_worker import solve as solve_queens_worker

    board = json.loads(PAGE_FIXTURE.read_text())
    response = solve_queens_worker(Path("unused.png"), parsed_board=board)

    assert response["solved"], response["error"]
    assert response["details"]["input_source"] == "page"
    assert [move["col"] for move in sorted(response["moves"], key=lambda move: move["row"])] == OFFICIAL_2026_11_20


@pytest.mark.parametrize("payload", [
    None, {}, {"size": 4},
    {"size": 3, "regions": [[0, 1, 2]] * 3},
    {"size": 4, "regions": [[0, 1, 2, 3]] * 3},
    {"size": 4, "regions": [[0, 1, 2, 3]] * 3 + [[0, 1, 2]]},
    {"size": 4, "regions": [[0, 1, 2, 2]] * 4},
    {"size": 4, "regions": [[0, 1, 2, -1]] * 4},
    {"size": 4, "regions": [[0, 1, 2, True]] * 4},
    {"size": 4, "regions": [[0, 1, 2, 3]] * 4, "solution": []},
])
def test_invalid_page_boards_are_rejected(payload: object) -> None:
    from services.solver_api.app.domain.errors import InvalidBoard
    from services.solver_api.app.domain.queens_board import validate_queens_board
    from services.solver_api.app.workers.solve_queens_worker import solve as solve_queens_worker

    with pytest.raises(InvalidBoard):
        validate_queens_board(payload)
    if isinstance(payload, dict):
        assert solve_queens_worker(Path("unused.png"), parsed_board=payload)["solved"] is False
