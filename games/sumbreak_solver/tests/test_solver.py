from __future__ import annotations

import json
import random
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from games.sumbreak_solver.src.sumbreak_solver import SumbreakMove, SumbreakSolver, apply_moves
from services.solver_api.app.domain.errors import InvalidBoard
from services.solver_api.app.domain.sumbreak_board import validate_sumbreak_board
from services.solver_api.app.workers.solve_sumbreak_worker import solve as solve_sumbreak_worker


FIXTURE = Path(__file__).parent / "fixtures" / "linkedin-2026-11-18.json"


def remaining_tiles(board: list[list[int | None]]) -> list[int]:
    return [value for row in board for value in row if value is not None]


def generate_solvable_board(rows: int, columns: int, rng: random.Random) -> list[list[int | None]]:
    """Run the game backwards: split a tile into two equal adjacent halves."""
    board: list[list[int | None]] = [[None] * columns for _ in range(rows)]
    board[rng.randrange(rows)][rng.randrange(columns)] = 1 << (rows * columns)
    placed = 1
    while placed < rows * columns:
        row, col = rng.choice([(r, c) for r in range(rows) for c in range(columns) if (board[r][c] or 0) > 1])
        empty = [
            (row + dr, col + dc)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= row + dr < rows and 0 <= col + dc < columns and board[row + dr][col + dc] is None
        ]
        if not empty:
            continue
        other_row, other_col = rng.choice(empty)
        half = board[row][col] // 2
        board[row][col] = half
        board[other_row][other_col] = half
        placed += 1
    smallest = min(remaining_tiles(board))
    return [[None if value is None else value // smallest for value in line] for line in board]


class SumbreakSolverTests(unittest.TestCase):
    def assert_solves(self, board: list[list[int | None]]) -> None:
        result = SumbreakSolver().solve(board)
        self.assertTrue(result.solved, result.error)
        final = apply_moves(board, result.moves)
        self.assertEqual(remaining_tiles(final), [sum(remaining_tiles(board))])
        self.assertEqual(final[result.final_cell[0]][result.final_cell[1]], result.final_value)

    def test_linkedin_launch_puzzle(self) -> None:
        board = json.loads(FIXTURE.read_text())["board"]
        result = SumbreakSolver().solve(board)
        self.assertTrue(result.solved)
        self.assertEqual(len(result.moves), 8)
        self.assertEqual(result.final_value, 128)
        self.assertEqual(remaining_tiles(apply_moves(board, result.moves)), [128])

    def test_single_tile_is_already_solved(self) -> None:
        result = SumbreakSolver().solve([[None, 8], [None, None]])
        self.assertTrue(result.solved)
        self.assertEqual(result.moves, [])
        self.assertEqual(result.final_cell, (0, 1))

    def test_holes_and_rectangular_boards(self) -> None:
        self.assert_solves([[1, 1, None], [2, 4, 8], [None, None, 16]])
        self.assert_solves([[2, 1, 1], [4, 8, None]])

    def test_non_power_of_two_values_follow_the_same_rules(self) -> None:
        self.assert_solves([[3, 3, 6]])

    def test_merge_order_and_direction_matter(self) -> None:
        # 2-2 must merge to the left so the 4 sits next to the other 4.
        board = [[4, 2, 2], [8, None, None]]
        result = SumbreakSolver().solve(board)
        self.assertTrue(result.solved)
        self.assertEqual(result.moves[0], SumbreakMove(source=(0, 2), target=(0, 1), value=4))
        self.assertEqual(remaining_tiles(apply_moves(board, result.moves)), [16])

    def test_unsolvable_boards(self) -> None:
        cases = {
            "disconnected": [[1, None, 1]],
            "odd sum": [[1, 1, 1]],
            "values that never pair": [[2, 1, 1, 4, 2, 2]],
            "trapped tile": [[1, 2, 1]],
        }
        for name, board in cases.items():
            with self.subTest(name):
                result = SumbreakSolver().solve(board)
                self.assertFalse(result.solved)
                self.assertTrue(result.error)

    def test_rejects_invalid_values(self) -> None:
        for board in ([[0, 1]], [[True, 1]], [[1.0, 1]], [[1], [1, 1]], [[None, None]], []):
            with self.subTest(board=board):
                self.assertFalse(SumbreakSolver().solve(board).solved)

    def test_time_limit_is_reported(self) -> None:
        board = generate_solvable_board(6, 6, random.Random(3))
        result = SumbreakSolver(time_limit_seconds=0).solve(board)
        if not result.solved:
            self.assertIn("time limit", result.error)

    def test_random_solvable_boards(self) -> None:
        rng = random.Random(2026)
        for rows, columns in ((3, 3), (4, 4), (3, 5), (5, 5)):
            for _ in range(6):
                board = generate_solvable_board(rows, columns, rng)
                with self.subTest(board=board):
                    started = time.monotonic()
                    self.assert_solves(board)
                    self.assertLess(time.monotonic() - started, 5)

    def test_apply_moves_rejects_illegal_moves(self) -> None:
        board = [[1, 2], [1, None]]
        for move in (
            SumbreakMove(source=(0, 0), target=(0, 1), value=3),
            SumbreakMove(source=(0, 1), target=(1, 0), value=4),
            SumbreakMove(source=(1, 1), target=(1, 0), value=2),
        ):
            with self.subTest(move=move), self.assertRaises(ValueError):
                apply_moves(board, [move])


class SumbreakPageBoardTests(unittest.TestCase):
    def test_valid_board_is_copied(self) -> None:
        payload = {"board": [[1, None], [1, 2]]}
        validated = validate_sumbreak_board(payload)
        self.assertEqual(validated, payload)
        self.assertIsNot(validated["board"][0], payload["board"][0])

    def test_invalid_boards(self) -> None:
        for payload in (
            None, [], {}, {"board": [[1, 1]], "lengths": []}, {"board": [[1, 1]]},
            {"board": [[1, 1], [1]]}, {"board": [[1, 0], [1, 1]]}, {"board": [[1, True], [1, 1]]},
            {"board": [[1, "2"], [1, 1]]}, {"board": [[None, None], [None, None]]},
            {"board": [[1] * 9] * 2}, {"board": [[1, 1 << 30], [1, 1]]},
        ):
            with self.subTest(payload=payload), self.assertRaises(InvalidBoard):
                validate_sumbreak_board(payload)


class SumbreakWorkerTests(unittest.TestCase):
    def test_worker_returns_ordered_moves(self) -> None:
        board = json.loads(FIXTURE.read_text())
        response = solve_sumbreak_worker("unused.png", parsed_board=board)
        self.assertTrue(response["solved"])
        self.assertEqual(response["puzzle"], "sumbreak")
        self.assertEqual(response["board_size"], 3)
        self.assertEqual(response["details"]["rows"], 3)
        self.assertEqual(response["details"]["board"], board["board"])
        moves = [
            SumbreakMove(source=(m["row"], m["col"]), target=(m["to_row"], m["to_col"]), value=m["value"])
            for m in response["moves"]
        ]
        self.assertEqual(remaining_tiles(apply_moves(board["board"], moves)), [128])

    def test_worker_requires_page_data(self) -> None:
        response = solve_sumbreak_worker("unused.png")
        self.assertFalse(response["solved"])
        self.assertFalse(response["details"]["parse_reliable"])
        self.assertEqual(response["moves"], [])

    def test_worker_reports_unsolvable_page_boards(self) -> None:
        response = solve_sumbreak_worker("unused.png", parsed_board={"board": [[1, None, 1], [None, None, None]]})
        self.assertFalse(response["solved"])
        self.assertTrue(response["details"]["parse_reliable"])
        self.assertIn("disconnected", response["error"])


if __name__ == "__main__":
    unittest.main()
