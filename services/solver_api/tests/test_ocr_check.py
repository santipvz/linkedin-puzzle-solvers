"""The page board checks what OCR read; it never replaces the OCR solve."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.solver_api.app.domain.errors import InvalidBoard
from services.solver_api.app.domain.ocr_check import check_ocr, compare_board_facts
from services.solver_api.app.domain.patches_board import patches_board_facts, patches_page_facts, validate_patches_board
from services.solver_api.app.domain.queens_board import queens_board_facts, queens_page_facts, validate_queens_board
from services.solver_api.app.domain.sudoku_board import sudoku_board_facts, sudoku_page_facts, validate_sudoku_board
from services.solver_api.app.domain.tango_board import MOON, SUN, tango_board_facts, tango_page_facts, validate_tango_board
from services.solver_api.app.domain.zip_board import validate_zip_board, zip_board_facts, zip_page_facts
from services.solver_api.app.workers import (
    solve_patches_worker,
    solve_queens_worker,
    solve_sudoku_worker,
    solve_tango_worker,
    solve_zip_worker,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def fixture(game: str) -> dict:
    return json.loads((REPO_ROOT / "games" / game / "tests/fixtures/linkedin-2026-11-20.json").read_text())


# --- Comparing facts -------------------------------------------------------

def test_comparison_lists_wrong_missed_and_invented_facts() -> None:
    page = {"r0c0 clue": 1, "r0c1 clue": 2, "r1c1 clue": 3}
    ocr = {"r0c0 clue": 1, "r0c1 clue": 7, "r2c2 clue": 4}
    check = compare_board_facts(page, ocr)
    assert check["matches"] is False
    assert check["checked"] == 3
    assert check["mismatches"] == [
        {"at": "r0c1 clue", "page": 2, "ocr": 7},
        {"at": "r1c1 clue", "page": 3, "ocr": None},
        {"at": "r2c2 clue", "page": None, "ocr": 4},
    ]
    assert compare_board_facts(page, dict(page))["matches"] is True


def test_an_invalid_page_board_is_ignored_with_a_reason() -> None:
    check = check_ocr(validate_zip_board, {"size": 99}, zip_page_facts, {})
    assert check["matches"] is None
    assert "Page board ignored" in check["error"]


# --- Page boards and OCR output describe the same facts --------------------

def test_zip_page_and_ocr_facts_agree() -> None:
    page = validate_zip_board({"size": 3, "sequence": [0, 8], "walls": [[1, "down"], [4, "left"]]})
    blocked_h = [[False, True, False], [False, False, False]]
    blocked_v = [[False, False], [True, False], [False, False]]
    assert zip_page_facts(page) == zip_board_facts({(0, 0): 1, (2, 2): 2}, blocked_h, blocked_v)
    # A wall reported from the other side is the same wall.
    assert zip_page_facts(validate_zip_board({"size": 3, "sequence": [0, 8], "walls": [[4, "up"], [3, "right"]]})) == zip_page_facts(page)


def test_tango_page_and_ocr_facts_agree() -> None:
    page = validate_tango_board({"size": 6, "suns": [0], "moons": [7], "equal": [[1, 2]], "opposite": [[8, 2]]})
    ocr = tango_board_facts([(0, 0, SUN), (1, 1, MOON)], [("=", (0, 2), (0, 1)), ("x", (0, 2), (1, 2))])
    assert tango_page_facts(page) == ocr


def test_queens_regions_match_whatever_their_ids() -> None:
    page = validate_queens_board({"size": 4, "regions": [[5, 5, 9, 9], [5, 2, 2, 9], [7, 2, 2, 9], [7, 7, 7, 9]]})
    ocr = [[0, 0, 1, 1], [0, 2, 2, 1], [3, 2, 2, 1], [3, 3, 3, 1]]
    assert queens_page_facts(page) == queens_board_facts(ocr)
    ocr[1][1] = 0
    assert compare_board_facts(queens_page_facts(page), queens_board_facts(ocr))["mismatches"] == [
        {"at": "r1c1 region", "page": 2, "ocr": 0},
    ]


def test_patches_page_and_ocr_facts_agree() -> None:
    page = validate_patches_board({"size": 4, "clues": [[0, "square", None], [6, "wide", 4]]})
    ocr = [{"row": 0, "col": 0, "shape": "square", "area": None}, {"row": 1, "col": 2, "shape": "wide", "area": 4}]
    assert patches_page_facts(page) == patches_board_facts(ocr)


def test_sudoku_page_and_ocr_facts_agree() -> None:
    board = [[0, 1, 0, 0, 0, 0]] + [[0] * 6 for _ in range(5)]
    assert sudoku_page_facts(validate_sudoku_board({"board": board})) == sudoku_board_facts(board) == {"r0c1 digit": 1}


# --- Validators --------------------------------------------------------------

@pytest.mark.parametrize(("validate", "payload"), [
    (validate_zip_board, {"size": 3, "sequence": [0, 9], "walls": []}),
    (validate_zip_board, {"size": 3, "sequence": [0, 1], "walls": [[1, "diagonal"]]}),
    (validate_zip_board, {"size": 3, "sequence": [0, 1], "walls": [], "solution": []}),
    (validate_tango_board, {"size": 6, "suns": [3], "moons": [3], "equal": [], "opposite": []}),
    (validate_tango_board, {"size": 6, "suns": [], "moons": [], "equal": [[5, 6]], "opposite": []}),
    (validate_queens_board, {"size": 4, "regions": [[0, 1, 2, 2]] * 4}),
    (validate_queens_board, {"size": 4, "regions": [[0, 1, 2, True]] * 4}),
    (validate_patches_board, {"size": 6, "clues": [[0, "round", None]]}),
    (validate_patches_board, {"size": 6, "clues": [[0, "any", None], [0, "square", 4]]}),
    (validate_sudoku_board, {"board": [[0] * 6] * 6}),
    (validate_sudoku_board, {"board": [[7] + [0] * 5] + [[0] * 6] * 5}),
])
def test_invalid_page_boards_are_rejected(validate, payload) -> None:
    with pytest.raises(InvalidBoard):
        validate(payload)


def test_real_page_boards_are_valid() -> None:
    for validate, game in ((validate_zip_board, "zip_solver"), (validate_tango_board, "tango_solver"),
                           (validate_queens_board, "queen_solver"), (validate_patches_board, "patches_solver"),
                           (validate_sudoku_board, "sudoku_solver")):
        validate(fixture(game))


# --- Workers: OCR solves, the page board only reports ------------------------

WORKERS = [
    (solve_zip_worker, "zip_solver"),
    (solve_tango_worker, "tango_solver"),
    (solve_queens_worker, "queen_solver"),
    (solve_patches_worker, "patches_solver"),
    (solve_sudoku_worker, "sudoku_solver"),
]


@pytest.mark.parametrize(("worker", "game"), WORKERS, ids=[game for _, game in WORKERS])
def test_workers_solve_from_the_image_and_report_the_check(worker, game) -> None:
    sample = REPO_ROOT / "games" / game / "examples/sample1.png"
    without = worker.solve(sample)
    # The 2026-11-20 page board is a different puzzle from the sample image.
    response = worker.solve(sample, parsed_board=fixture(game))

    assert response["solved"] and without["solved"]
    assert response["moves"] == without["moves"]
    check = response["details"]["ocr_check"]
    assert check["matches"] is False and check["mismatch_count"] > 0
    assert "ocr_check" not in without["details"]


@pytest.mark.parametrize(("worker", "game"), WORKERS, ids=[game for _, game in WORKERS])
def test_an_invalid_page_board_never_stops_the_ocr_solve(worker, game) -> None:
    response = worker.solve(REPO_ROOT / "games" / game / "examples/sample1.png", parsed_board={"unexpected": True})
    assert response["solved"]
    assert response["details"]["ocr_check"]["matches"] is None


def test_a_page_board_that_matches_the_ocr_reading_is_reported_as_matching() -> None:
    sample = REPO_ROOT / "games/sudoku_solver/examples/sample1.png"
    read = solve_sudoku_worker.solve(sample)
    board = [[0] * 6 for _ in range(6)]
    for cell in read["fixed_cells"]:
        board[cell["row"]][cell["col"]] = cell["value"]
    check = solve_sudoku_worker.solve(sample, parsed_board={"board": board})["details"]["ocr_check"]
    assert check == {"matches": True, "checked": len(read["fixed_cells"]), "mismatch_count": 0, "mismatches": []}

    sample = REPO_ROOT / "games/queen_solver/examples/sample1.png"
    read = solve_queens_worker.solve(sample)
    page = {"size": read["board_size"], "regions": read["details"]["region_grid"]}
    assert solve_queens_worker.solve(sample, parsed_board=page)["details"]["ocr_check"]["matches"] is True
