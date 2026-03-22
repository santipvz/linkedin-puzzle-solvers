"""Solution validation for Queens puzzles."""

from typing import Dict, List

import numpy as np

from src.core.interfaces import SolutionValidator
from src.core.models import Region


class QueensSolutionValidator(SolutionValidator):
    """Validator for Queens puzzle solutions."""

    def validate(self, solution: np.ndarray, regions: Dict[int, Region]) -> bool:
        """Validate a complete solution against all Queens rules."""
        if solution is None:
            return False

        board_size = solution.shape[0]

        # Check basic structure
        if not self._validate_structure(solution, board_size):
            return False

        # Check all Queens rules
        if not self._validate_rows(solution, board_size):
            return False

        if not self._validate_columns(solution, board_size):
            return False

        if not self._validate_regions(solution, regions):
            return False

        if not self._validate_adjacency(solution, board_size):
            return False

        return True

    def validate_with_details(self, solution: np.ndarray,
                            regions: Dict[int, Region]) -> tuple[bool, List[str]]:
        """Validate solution and return detailed error messages."""
        errors = []

        if solution is None:
            errors.append("Solution is None")
            return False, errors

        board_size = solution.shape[0]

        # Structure validation
        if not self._validate_structure(solution, board_size):
            errors.append("Invalid solution structure")

        # Row validation
        row_errors = self._validate_rows_detailed(solution, board_size)
        errors.extend(row_errors)

        # Column validation
        col_errors = self._validate_columns_detailed(solution, board_size)
        errors.extend(col_errors)

        # Region validation
        region_errors = self._validate_regions_detailed(solution, regions)
        errors.extend(region_errors)

        # Adjacency validation
        adj_errors = self._validate_adjacency_detailed(solution, board_size)
        errors.extend(adj_errors)

        return len(errors) == 0, errors

    def _validate_structure(self, solution: np.ndarray, board_size: int) -> bool:
        """Validate basic structure of solution."""
        # Check dimensions
        if solution.shape != (board_size, board_size):
            return False

        # Check values (only 0 and 1)
        if not np.all(np.isin(solution, [0, 1])):
            return False

        # Check total number of queens
        if np.sum(solution) != board_size:
            return False

        return True

    def _validate_rows(self, solution: np.ndarray, board_size: int) -> bool:
        """Validate exactly one queen per row."""
        for r in range(board_size):
            if np.sum(solution[r, :]) != 1:
                return False
        return True

    def _validate_rows_detailed(self, solution: np.ndarray, board_size: int) -> List[str]:
        """Validate rows with detailed error messages."""
        errors = []
        for r in range(board_size):
            count = np.sum(solution[r, :])
            if count != 1:
                errors.append(f"Row {r+1} has {count} queens (expected 1)")
        return errors

    def _validate_columns(self, solution: np.ndarray, board_size: int) -> bool:
        """Validate exactly one queen per column."""
        for c in range(board_size):
            if np.sum(solution[:, c]) != 1:
                return False
        return True

    def _validate_columns_detailed(self, solution: np.ndarray, board_size: int) -> List[str]:
        """Validate columns with detailed error messages."""
        errors = []
        for c in range(board_size):
            count = np.sum(solution[:, c])
            if count != 1:
                errors.append(f"Column {c+1} has {count} queens (expected 1)")
        return errors

    def _validate_regions(self, solution: np.ndarray, regions: Dict[int, Region]) -> bool:
        """Validate exactly one queen per region."""
        for region in regions.values():
            region_queens = sum(solution[r, c] for r, c in region.positions)
            if region_queens != 1:
                return False
        return True

    def _validate_regions_detailed(self, solution: np.ndarray,
                                 regions: Dict[int, Region]) -> List[str]:
        """Validate regions with detailed error messages."""
        errors = []
        for region in regions.values():
            count = sum(solution[r, c] for r, c in region.positions)
            if count != 1:
                errors.append(f"Region {region.id} has {count} queens (expected 1)")
        return errors

    def _validate_adjacency(self, solution: np.ndarray, board_size: int) -> bool:
        """Validate no adjacent queens."""
        queen_positions = self._get_queen_positions(solution, board_size)

        for i, (r1, c1) in enumerate(queen_positions):
            for j, (r2, c2) in enumerate(queen_positions[i+1:], i+1):
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    return False

        return True

    def _validate_adjacency_detailed(self, solution: np.ndarray, board_size: int) -> List[str]:
        """Validate adjacency with detailed error messages."""
        errors = []
        queen_positions = self._get_queen_positions(solution, board_size)

        for i, (r1, c1) in enumerate(queen_positions):
            for j, (r2, c2) in enumerate(queen_positions[i+1:], i+1):
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    errors.append(f"Adjacent queens at ({r1+1},{c1+1}) and ({r2+1},{c2+1})")

        return errors

    def _get_queen_positions(self, solution: np.ndarray, board_size: int) -> List[tuple]:
        """Get list of queen positions."""
        positions = []
        for r in range(board_size):
            for c in range(board_size):
                if solution[r, c] == 1:
                    positions.append((r, c))
        return positions
