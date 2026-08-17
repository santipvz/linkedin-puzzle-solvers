from __future__ import annotations

from typing import TypeAlias

import numpy as np

from core.commons import uniform_grid_bounds


CellRect: TypeAlias = tuple[int, int, int, int]


class GridDetector:
    """Compatibility wrapper around the shared uniform-grid geometry."""

    def __init__(self, grid_size: int = 6) -> None:
        self.grid_size = int(grid_size)

    def detect_grid(self, image: np.ndarray) -> list[list[CellRect]]:
        grid = uniform_grid_bounds(
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            board_size=self.grid_size,
        )
        return [list(row) for row in grid.cells()]

    @staticmethod
    def get_cell_image(image: np.ndarray, grid_coords: list[list[CellRect]], row: int, col: int) -> np.ndarray:
        if row < 0 or col < 0:
            raise ValueError(f"Cell coordinates out of range: ({row}, {col})")
        try:
            x, y, width, height = grid_coords[row][col]
        except IndexError as exc:
            raise ValueError(f"Cell coordinates out of range: ({row}, {col})") from exc
        return image[y : y + height, x : x + width]

    @staticmethod
    def get_border_region(
        image: np.ndarray,
        grid_coords: list[list[CellRect]],
        pos1: tuple[int, int],
        pos2: tuple[int, int],
    ) -> np.ndarray:
        row1, col1 = pos1
        row2, col2 = pos2
        if abs(row1 - row2) + abs(col1 - col2) != 1:
            raise ValueError(f"Cells {pos1} and {pos2} are not adjacent")
        x, y, width, height = grid_coords[row1][col1]
        if row1 == row2:
            return image[y : y + height, x + width - 10 : x + width + 10]
        return image[y + height - 10 : y + height + 10, x : x + width]
