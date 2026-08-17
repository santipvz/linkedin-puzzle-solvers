from __future__ import annotations

from pathlib import Path

from games.sudoku_solver.src.image_parser import MiniSudokuImageParser
from games.sudoku_solver.src.mini_sudoku_solver import MiniSudokuSolver
from services.solver_api.app.workers.solve_sudoku_worker import solve as solve_sudoku_worker


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample1.png"
SOLUTION = [
    [1, 2, 3, 4, 5, 6],
    [4, 5, 6, 1, 2, 3],
    [2, 3, 4, 5, 6, 1],
    [5, 6, 1, 2, 3, 4],
    [3, 4, 5, 6, 1, 2],
    [6, 1, 2, 3, 4, 5],
]


def test_solver_completes_valid_board_and_preserves_clues() -> None:
    board = [list(row) for row in SOLUTION]
    board[0][0] = 0
    board[3][4] = 0

    result = MiniSudokuSolver().solve(board, max_solutions=2)

    assert result.solved
    assert result.board == SOLUTION
    assert result.solution_count == 1


def test_solver_rejects_conflicting_clues_and_invalid_shape() -> None:
    conflicting = [list(row) for row in SOLUTION]
    conflicting[0][1] = conflicting[0][0]

    conflict_result = MiniSudokuSolver().solve(conflicting)
    shape_result = MiniSudokuSolver().solve([[0] * 6 for _ in range(5)])

    assert not conflict_result.solved
    assert "Conflicting clue" in str(conflict_result.error)
    assert not shape_result.solved
    assert "6x6" in str(shape_result.error)


def test_parser_and_worker_solve_tracked_sample() -> None:
    assert SAMPLE_PATH.is_file(), f"Missing tracked Sudoku sample: {SAMPLE_PATH}"

    parsed = MiniSudokuImageParser().parse_image(SAMPLE_PATH)
    response = solve_sudoku_worker(SAMPLE_PATH)

    assert len(parsed["board"]) == 6
    assert all(len(row) == 6 for row in parsed["board"])
    assert len(parsed["grid_lines"]["rows"]) == 7
    assert len(parsed["grid_lines"]["cols"]) == 7
    assert parsed["fixed_cells"]
    assert response["solved"]
    assert response["board_size"] == 6
    assert response["details"]["parse_reliable"]
    assert response["details"]["unique_solution"]
    assert response["moves"]
