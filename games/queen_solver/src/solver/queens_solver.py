"""Queens puzzle solver using backtracking with validation."""

import time

import numpy as np

from src.core.interfaces import PuzzleSolver
from src.core.models import Region, SolverResult


class BacktrackingQueensSolver(PuzzleSolver):
    def __init__(self) -> None:
        self.iteration_count = 0
        self.max_iterations = 10000000

    def solve(self, board_size: int, regions: dict[int, Region]) -> SolverResult:
        start_time = time.time()
        self.iteration_count = 0

        if not self._pre_validate_solvability(board_size, regions):
            return SolverResult(
                success=False,
                solution=None,
                execution_time=time.time() - start_time,
                iterations=0,
                validation_passed=False,
                error_message="Puzzle cannot have a valid solution",
            )

        region_map = self._create_region_map(board_size, regions)

        solution = np.zeros((board_size, board_size), dtype=int)

        if self._solve_backtracking_full(solution, 0, board_size, regions, region_map):
            validation_passed = self._post_validate_solution(solution, board_size, regions)

            return SolverResult(
                success=True,
                solution=solution,
                execution_time=time.time() - start_time,
                iterations=self.iteration_count,
                validation_passed=validation_passed,
                error_message=None if validation_passed else "Solution found but validation failed",
            )

        # Keep failures strict; relaxed mode can return invalid placements.
        return SolverResult(
            success=False,
            solution=None,
            execution_time=time.time() - start_time,
            iterations=self.iteration_count,
            validation_passed=False,
            error_message="No valid solution exists with current constraints",
        )

    def _pre_validate_solvability(self, board_size: int, regions: dict[int, Region]) -> bool:
        """Validate if puzzle can have a solution before solving."""
        if len(regions) != board_size:
            return False

        for region in regions.values():
            if region.size == 0:
                return False

        # Keep pre-validation conservative to avoid false negatives.
        # Detailed feasibility should be decided by backtracking.
        return True

    def _validate_region_conflicts(self, regions: dict[int, Region]) -> bool:
        column_regions = {}
        row_regions = {}

        for region_id, region in regions.items():
            for r, c in region.positions:
                if c not in column_regions:
                    column_regions[c] = []
                if r not in row_regions:
                    row_regions[r] = []

                column_regions[c].append(region_id)
                row_regions[r].append(region_id)

        for region_ids in column_regions.values():
            unique_regions = list(set(region_ids))
            if len(unique_regions) > 1:
                region_sizes = [regions[rid].size for rid in unique_regions]

                if 1 in region_sizes and any(size <= 3 for size in region_sizes if size != 1):
                    return False

        return True

    def _create_region_map(self, board_size: int, regions: dict[int, Region]) -> np.ndarray:
        """Create a 2D array mapping each cell to its region ID."""
        region_map = np.zeros((board_size, board_size), dtype=int)

        for region_id, region in regions.items():
            for r, c in region.positions:
                region_map[r, c] = region_id

        return region_map

    def _solve_backtracking_full(self, solution: np.ndarray, row: int, board_size: int,
                               regions: dict[int, Region], region_map: np.ndarray) -> bool:
        """Backtracking with all constraints."""
        del row

        region_ids = sorted(regions.keys())
        region_bit_by_id = {region_id: 1 << index for index, region_id in enumerate(region_ids)}
        all_regions_mask = (1 << len(region_ids)) - 1
        row_cells: list[list[tuple[int, int, int]]] = []

        for current_row in range(board_size):
            cells = []
            for col in range(board_size):
                region_id = int(region_map[current_row, col])
                region = regions[region_id]
                cells.append((col, region_bit_by_id[region_id], int(region.size)))
            cells.sort(key=lambda item: (item[2], item[0]))
            row_cells.append(cells)

        placements = [-1 for _ in range(board_size)]

        def has_remaining_region_options(
            next_row: int,
            used_cols_mask: int,
            used_regions_mask: int,
            previous_col: int,
        ) -> bool:
            for region_id in region_ids:
                region_bit = region_bit_by_id[region_id]
                if used_regions_mask & region_bit:
                    continue

                has_option = False
                for region_row, region_col in regions[region_id].positions:
                    if region_row < next_row:
                        continue
                    if used_cols_mask & (1 << region_col):
                        continue
                    if region_row == next_row and previous_col >= 0 and abs(previous_col - region_col) <= 1:
                        continue

                    has_option = True
                    break

                if not has_option:
                    return False

            return True

        def backtrack(current_row: int, used_cols_mask: int, used_regions_mask: int, previous_col: int) -> bool:
            self.iteration_count += 1
            if self.iteration_count > self.max_iterations:
                return False

            if current_row == board_size:
                return used_regions_mask == all_regions_mask

            for col, region_bit, _region_size in row_cells[current_row]:
                col_bit = 1 << col
                if used_cols_mask & col_bit:
                    continue
                if used_regions_mask & region_bit:
                    continue
                if previous_col >= 0 and abs(previous_col - col) <= 1:
                    continue

                next_used_regions = used_regions_mask | region_bit
                next_used_cols = used_cols_mask | col_bit
                if not has_remaining_region_options(current_row + 1, next_used_cols, next_used_regions, col):
                    continue

                placements[current_row] = col
                if backtrack(current_row + 1, next_used_cols, next_used_regions, col):
                    return True
                placements[current_row] = -1

            return False

        if not backtrack(0, 0, 0, -1):
            return False

        solution[:, :] = 0
        for solved_row, solved_col in enumerate(placements):
            if solved_col < 0:
                return False
            solution[solved_row, solved_col] = 1
        return True

    def _solve_backtracking_basic(self, solution: np.ndarray, row: int, board_size: int) -> bool:
        """Backtracking with basic constraints only."""
        self.iteration_count += 1

        if self.iteration_count > self.max_iterations:
            return False

        if row == board_size:
            return True

        for col in range(board_size):
            if self._is_valid_basic(solution, row, col, board_size):
                solution[row, col] = 1

                if self._solve_backtracking_basic(solution, row + 1, board_size):
                    return True

                solution[row, col] = 0

        return False

    def _is_valid_full(self, solution: np.ndarray, row: int, col: int, board_size: int,
                      regions: dict[int, Region], region_map: np.ndarray) -> bool:
        """Validate placement with all constraints."""
        for r in range(row):
            if solution[r, col] == 1:
                return False

        region_id = region_map[row, col]
        region = regions[region_id]
        for r, c in region.positions:
            if solution[r, c] == 1:
                return False

        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                     (0, 1), (1, -1), (1, 0), (1, 1)]

        for dr, dc in directions:
            nr, nc = row + dr, col + dc
            if (0 <= nr < board_size and 0 <= nc < board_size and
                solution[nr, nc] == 1):
                return False

        return True

    def _is_valid_basic(self, solution: np.ndarray, row: int, col: int, board_size: int) -> bool:
        """Validate placement with basic constraints only."""
        for r in range(row):
            if solution[r, col] == 1:
                return False

        # Check adjacency constraint (only previous rows)
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1)]

        for dr, dc in directions:
            nr, nc = row + dr, col + dc
            if (0 <= nr < board_size and 0 <= nc < board_size and
                solution[nr, nc] == 1):
                return False

        return True

    def _post_validate_solution(self, solution: np.ndarray, board_size: int,
                              regions: dict[int, Region]) -> bool:
        """Validation of found solution."""
        if np.sum(solution) != board_size:
            return False

        # Check rows (exactly 1 queen per row)
        for r in range(board_size):
            if np.sum(solution[r, :]) != 1:
                return False

        # Check columns (exactly 1 queen per column)
        for c in range(board_size):
            if np.sum(solution[:, c]) != 1:
                return False

        # Check regions (exactly 1 queen per region)
        for region in regions.values():
            region_queens = sum(solution[r, c] for r, c in region.positions)
            if region_queens != 1:
                return False

        # Check adjacency (no queens touching)
        queen_positions = []
        for r in range(board_size):
            for c in range(board_size):
                if solution[r, c] == 1:
                    queen_positions.append((r, c))

        for i, (r1, c1) in enumerate(queen_positions):
            for j, (r2, c2) in enumerate(queen_positions[i+1:], i+1):
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    return False

        return True
