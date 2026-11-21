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
