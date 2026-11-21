"""Backtracking solver for LinkedIn Queens.

Rules: one queen per row, per column and per colour region, and no two
queens touching, diagonals included.

The search places one queen per row, top to bottom, tracking used columns
and regions as bitmasks. Within a row it tries cells of smaller regions
first, and it prunes a placement as soon as some unused region has no cell
left where a queen could still go.
"""

import time

import numpy as np

from src.core.models import Region, SolverResult
from src.solver.validator import QueensSolutionValidator


class BacktrackingQueensSolver:
    def __init__(self, max_iterations: int = 10_000_000) -> None:
        self.iteration_count = 0
        self.max_iterations = max_iterations

    def solve(self, board_size: int, regions: dict[int, Region]) -> SolverResult:
        start_time = time.time()
        self.iteration_count = 0

        def result(solution: np.ndarray | None, error: str | None, valid: bool = False) -> SolverResult:
            return SolverResult(
                success=solution is not None,
                solution=solution,
                execution_time=time.time() - start_time,
                iterations=self.iteration_count,
                validation_passed=valid,
                error_message=error,
            )

        # A board of size N needs exactly N non-empty regions.
        if len(regions) != board_size or any(not region.positions for region in regions.values()):
            return result(None, "Puzzle cannot have a valid solution")

        placements = self._search(board_size, regions)
        if placements is None:
            return result(None, "No valid solution exists with current constraints")

        solution = np.zeros((board_size, board_size), dtype=int)
        for row, col in enumerate(placements):
            solution[row, col] = 1
        valid = QueensSolutionValidator().validate(solution, regions)
        return result(solution, None if valid else "Solution found but validation failed", valid)

    def _search(self, board_size: int, regions: dict[int, Region]) -> list[int] | None:
        """Column of the queen in each row, or None when no placement works."""
        region_ids = sorted(regions)
        region_bit = {region_id: 1 << index for index, region_id in enumerate(region_ids)}
        all_regions_mask = (1 << len(region_ids)) - 1
        region_of = {cell: region_id for region_id, region in regions.items() for cell in region.positions}

        # Each row's cells as (col, region bit), smaller regions first.
        row_cells = [
            [
                (col, region_bit[region_of[row, col]])
                for col in sorted(range(board_size), key=lambda col: (regions[region_of[row, col]].size, col))
            ]
            for row in range(board_size)
        ]
        placements = [-1] * board_size

        def every_region_still_fits(next_row: int, used_cols: int, used_regions: int, previous_col: int) -> bool:
            for region_id in region_ids:
                if used_regions & region_bit[region_id]:
                    continue
                if not any(
                    row >= next_row
                    and not used_cols & (1 << col)
                    and not (row == next_row and abs(previous_col - col) <= 1)
                    for row, col in regions[region_id].positions
                ):
                    return False
            return True

        def backtrack(row: int, used_cols: int, used_regions: int, previous_col: int) -> bool:
            self.iteration_count += 1
            if self.iteration_count > self.max_iterations:
                return False
            if row == board_size:
                return used_regions == all_regions_mask

            for col, bit in row_cells[row]:
                if used_cols & (1 << col) or used_regions & bit:
                    continue
                if previous_col >= 0 and abs(previous_col - col) <= 1:
                    continue
                next_cols, next_regions = used_cols | (1 << col), used_regions | bit
                if not every_region_still_fits(row + 1, next_cols, next_regions, col):
                    continue
                placements[row] = col
                if backtrack(row + 1, next_cols, next_regions, col):
                    return True
            return False

        return placements if backtrack(0, 0, 0, -1) else None
