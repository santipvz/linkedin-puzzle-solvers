"""OCR regression: every board in tests/boards must be read and judged correctly."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.solver_api.app.workers.solve_queens_worker import solve


BOARDS = Path(__file__).resolve().parent / "boards"
# Known OCR misses, kept visible until they are fixed.
KNOWN_MISREADS = {
    # The single lavender cell at (1, 0) is a ninth region on an 8x8 board, so the
    # puzzle has no solution; OCR merges it into the blue region next to it.
    "uboard1.png": "lavender one-cell region is merged into the neighbouring blue region",
}


def boards(kind: str) -> list[object]:
    return [
        pytest.param(path, id=path.name, marks=pytest.mark.xfail(reason=KNOWN_MISREADS[path.name], strict=True))
        if path.name in KNOWN_MISREADS else pytest.param(path, id=path.name)
        for path in sorted((BOARDS / kind).glob("*.png"))
    ]


@pytest.mark.parametrize("image", boards("solvable"))
def test_solvable_boards_are_solved(image: Path) -> None:
    response = solve(image)
    assert response["solved"], response["error"]
    assert len(response["moves"]) == response["board_size"]


@pytest.mark.parametrize("image", boards("unsolvable"))
def test_unsolvable_boards_are_not_solved(image: Path) -> None:
    assert not solve(image)["solved"]
