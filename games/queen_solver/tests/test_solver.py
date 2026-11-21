from __future__ import annotations

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


def test_single_cell_regions_next_to_small_regions_are_not_rejected_up_front() -> None:
    # An earlier heuristic rejected boards mixing a one-cell region with small ones in a column.
    color = np.array([0, 0, 0], dtype=np.uint8)
    cells = {
        1: [(0, 1)],
        2: [(0, 0), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)],
        3: [(2, 0), (2, 1), (2, 2), (2, 3), (3, 0), (3, 1)],
        4: [(3, 2), (3, 3)],
    }
    regions = {key: Region(id=key, positions=value, color=color, size=0) for key, value in cells.items()}

    result = BacktrackingQueensSolver().solve(4, regions)

    assert result.success and result.validation_passed
    assert [int(col) for col in result.solution.argmax(axis=1)] == [1, 3, 0, 2]
