from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class MiniSudokuSolveResult:
    solved: bool
    board: list[list[int]] | None
    iterations: int
    error: str | None = None
    solution_count: int = 0


class MiniSudokuSolver:
    size = 6
    box_height = 2
    box_width = 3

    def __init__(self) -> None:
        self._iterations = 0

    @property
    def iterations(self) -> int:
        return self._iterations

    def solve(self, board: Iterable[Iterable[int]], *, max_solutions: int = 1) -> MiniSudokuSolveResult:
        max_solutions = max(1, int(max_solutions))
        working = [list(row) for row in board]
        if len(working) != self.size or any(len(row) != self.size for row in working):
            return MiniSudokuSolveResult(
                solved=False,
                board=None,
                iterations=0,
                error=f"Expected a {self.size}x{self.size} board.",
                solution_count=0,
            )

        digits = set(range(1, self.size + 1))
        rows_missing = [set(digits) for _ in range(self.size)]
        cols_missing = [set(digits) for _ in range(self.size)]
        boxes_missing = [set(digits) for _ in range(self.size)]
        empty_cells: list[tuple[int, int]] = []

        for row in range(self.size):
            for col in range(self.size):
                value = int(working[row][col])
                if value == 0:
                    empty_cells.append((row, col))
                    continue

                if value < 1 or value > self.size:
                    return MiniSudokuSolveResult(
                        solved=False,
                        board=None,
                        iterations=0,
                        error=f"Found invalid clue value {value} at ({row}, {col}).",
                        solution_count=0,
                    )

                box = self._box_index(row, col)
                if (
                    value not in rows_missing[row]
                    or value not in cols_missing[col]
                    or value not in boxes_missing[box]
                ):
                    return MiniSudokuSolveResult(
                        solved=False,
                        board=None,
                        iterations=0,
                        error=f"Conflicting clue value {value} at ({row}, {col}).",
                        solution_count=0,
                    )

                rows_missing[row].remove(value)
                cols_missing[col].remove(value)
                boxes_missing[box].remove(value)

        self._iterations = 0
        solution_count = 0
        first_solution: list[list[int]] | None = None

        def backtrack() -> None:
            nonlocal solution_count, first_solution
            if solution_count >= max_solutions:
                return

            if not empty_cells:
                solution_count += 1
                if first_solution is None:
                    first_solution = [list(row) for row in working]
                return

            best_index = -1
            best_candidates: set[int] | None = None

            for index, (row, col) in enumerate(empty_cells):
                candidates = rows_missing[row] & cols_missing[col] & boxes_missing[self._box_index(row, col)]
                if not candidates:
                    return
                if best_candidates is None or len(candidates) < len(best_candidates):
                    best_candidates = candidates
                    best_index = index
                if best_candidates is not None and len(best_candidates) == 1:
                    break

            if best_candidates is None or best_index < 0:
                return

            row, col = empty_cells.pop(best_index)
            box = self._box_index(row, col)

            for value in sorted(best_candidates):
                self._iterations += 1

                working[row][col] = value
                rows_missing[row].remove(value)
                cols_missing[col].remove(value)
                boxes_missing[box].remove(value)

                backtrack()

                working[row][col] = 0
                rows_missing[row].add(value)
                cols_missing[col].add(value)
                boxes_missing[box].add(value)

                if solution_count >= max_solutions:
                    break

            empty_cells.insert(best_index, (row, col))

        backtrack()
        if first_solution is not None:
            return MiniSudokuSolveResult(
                solved=True,
                board=first_solution,
                iterations=self._iterations,
                error=None,
                solution_count=solution_count,
            )

        return MiniSudokuSolveResult(
            solved=False,
            board=None,
            iterations=self._iterations,
            error="No valid solution found.",
            solution_count=0,
        )

    def _box_index(self, row: int, col: int) -> int:
        box_row = row // self.box_height
        box_col = col // self.box_width
        boxes_per_row = self.size // self.box_width
        return box_row * boxes_per_row + box_col
