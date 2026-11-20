from __future__ import annotations

import json
from pathlib import Path

import pytest

from games.zip_solver.src.image_parser import ZipImageParser
from games.zip_solver.src.zip_solver import ZipSolver
from services.solver_api.app.domain.errors import InvalidBoard
from services.solver_api.app.domain.zip_board import validate_zip_board, zip_solver_input
from services.solver_api.app.workers.solve_zip_worker import solve as solve_zip_worker


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample1.png"


def test_solver_follows_clues_and_visits_every_cell_once() -> None:
    result = ZipSolver().solve(
        size=2,
        blocked_h=[[False, False]],
        blocked_v=[[False], [False]],
        clues={(0, 0): 1, (0, 1): 2, (1, 1): 3, (1, 0): 4},
    )

    assert result.solved
    assert result.path == [(0, 0), (0, 1), (1, 1), (1, 0)]
    assert result.directions == ["right", "down", "left"]


def test_solver_rejects_invalid_walls_and_clue_sequences() -> None:
    invalid_walls = ZipSolver().solve(
        size=3,
        blocked_h=[],
        blocked_v=[[False, False] for _ in range(3)],
        clues={(0, 0): 1},
    )
    duplicate_clues = ZipSolver().solve(
        size=2,
        blocked_h=[[False, False]],
        blocked_v=[[False], [False]],
        clues={(0, 0): 1, (1, 1): 1},
    )

    assert not invalid_walls.solved
    assert "blocked_h" in str(invalid_walls.error)
    assert not duplicate_clues.solved
    assert "Duplicate" in str(duplicate_clues.error)


def test_parser_and_worker_solve_tracked_sample() -> None:
    assert SAMPLE_PATH.is_file(), f"Missing tracked Zip sample: {SAMPLE_PATH}"

    parsed = ZipImageParser().parse_image(SAMPLE_PATH)
    response = solve_zip_worker(SAMPLE_PATH)
    size = int(parsed["size"])

    assert parsed["board_size"] == size
    assert len(parsed["blocked_h"]) == size - 1
    assert all(len(row) == size for row in parsed["blocked_h"])
    assert len(parsed["blocked_v"]) == size
    assert all(len(row) == size - 1 for row in parsed["blocked_v"])
    assert parsed["clues"]
    assert response["solved"]
    assert response["details"]["parse_reliable"]
    assert len(response["path"]) == size * size
    assert len({(cell["row"], cell["col"]) for cell in response["path"]}) == size * size
    assert len(response["directions"]) == size * size - 1


PAGE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "linkedin-2026-11-20.json"
# LinkedIn's own answer for the 2026-11-20 puzzle, as cell indexes.
OFFICIAL_2026_11_20 = [
    12, 11, 10, 9, 16, 17, 18, 19, 26, 25, 24, 23, 22, 29, 36, 37, 30, 31, 38, 39, 32, 33, 34, 27, 20,
    13, 6, 5, 4, 3, 2, 1, 0, 7, 8, 15, 14, 21, 28, 35, 42, 43, 44, 45, 46, 47, 48, 41, 40,
]


def test_worker_solves_a_page_board_without_the_image() -> None:
    board = json.loads(PAGE_FIXTURE.read_text())
    response = solve_zip_worker(Path("unused.png"), parsed_board=board)

    assert response["solved"], response["error"]
    assert response["details"]["input_source"] == "page"
    assert [cell["row"] * 7 + cell["col"] for cell in response["path"]] == OFFICIAL_2026_11_20
    assert response["start_cell"] == {"row": 1, "col": 5}
    assert len(response["directions"]) == 48


def test_page_walls_in_every_direction_block_the_same_edge() -> None:
    # A wall can be reported from either side; both block the same move.
    for walls in ([[1, "down"]], [[4, "up"]], [[3, "right"]], [[4, "left"]]):
        blocked_h, blocked_v, _ = zip_solver_input(validate_zip_board({"size": 3, "sequence": [0, 8], "walls": walls}))
        assert sum(map(sum, blocked_h)) + sum(map(sum, blocked_v)) == 1
    blocked_h, blocked_v, clues = zip_solver_input(validate_zip_board({"size": 3, "sequence": [0, 8], "walls": [[1, "down"], [4, "left"]]}))
    assert blocked_h[0][1] and blocked_v[1][0]
    assert clues == {(0, 0): 1, (2, 2): 2}


@pytest.mark.parametrize("payload", [
    None, {}, {"size": 7, "sequence": [0, 1]},
    {"size": 2, "sequence": [0, 1], "walls": []},
    {"size": 3, "sequence": [0], "walls": []},
    {"size": 3, "sequence": [0, 0], "walls": []},
    {"size": 3, "sequence": [0, 9], "walls": []},
    {"size": 3, "sequence": [0, True], "walls": []},
    {"size": 3, "sequence": [0, 1], "walls": [[1, "diagonal"]]},
    {"size": 3, "sequence": [0, 1], "walls": [[9, "down"]]},
    {"size": 3, "sequence": [0, 1], "walls": [], "solution": [0, 1]},
])
def test_invalid_page_boards_are_rejected(payload: object) -> None:
    with pytest.raises(InvalidBoard):
        validate_zip_board(payload)
    if isinstance(payload, dict):
        assert solve_zip_worker(Path("unused.png"), parsed_board=payload)["solved"] is False
