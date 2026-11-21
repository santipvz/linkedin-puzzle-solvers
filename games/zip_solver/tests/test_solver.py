from __future__ import annotations

from pathlib import Path

from games.zip_solver.src.image_parser import ZipImageParser
from games.zip_solver.src.zip_solver import ZipSolver
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
