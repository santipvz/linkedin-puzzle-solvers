"""Checks a Queens solution against the rules."""

import numpy as np

from src.core.models import Region


class QueensSolutionValidator:
    def validate(self, solution: np.ndarray | None, regions: dict[int, Region]) -> bool:
        return self.validate_with_details(solution, regions)[0]

    def validate_with_details(self, solution: np.ndarray | None, regions: dict[int, Region]) -> tuple[bool, list[str]]:
        """Whether ``solution`` (1 = queen) is valid, and every rule it breaks."""
        if solution is None:
            return False, ["Solution is None"]
        size = solution.shape[0]
        if solution.shape != (size, size) or not np.isin(solution, (0, 1)).all() or solution.sum() != size:
            return False, ["Invalid solution structure"]

        errors = [f"Row {row + 1} has {count} queens (expected 1)" for row, count in enumerate(solution.sum(axis=1)) if count != 1]
        errors += [f"Column {col + 1} has {count} queens (expected 1)" for col, count in enumerate(solution.sum(axis=0)) if count != 1]
        for region in regions.values():
            count = sum(int(solution[row, col]) for row, col in region.positions)
            if count != 1:
                errors.append(f"Region {region.id} has {count} queens (expected 1)")
        queens = [tuple(map(int, cell)) for cell in np.argwhere(solution == 1)]
        for index, (r1, c1) in enumerate(queens):
            for r2, c2 in queens[index + 1:]:
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    errors.append(f"Adjacent queens at ({r1 + 1},{c1 + 1}) and ({r2 + 1},{c2 + 1})")
        return not errors, errors
