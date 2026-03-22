from typing import List, Tuple
import numpy as np


class GridDetector:
    """
    Grid detector for Tango board.

    Divides the board image into a grid of size `grid_size` x `grid_size` and
    returns the coordinates of each cell.
    """

    def __init__(self, grid_size: int = 6):
        self.grid_size = grid_size

    def detect_grid(self, img: np.ndarray) -> List[List[Tuple[int, int, int, int]]]:
        height, width = img.shape[:2]

        cell_width = width // self.grid_size
        cell_height = height // self.grid_size

        grid_coords = []
        for row in range(self.grid_size):
            row_coords = []
            for col in range(self.grid_size):
                x = col * cell_width
                y = row * cell_height
                row_coords.append((x, y, cell_width, cell_height))
            grid_coords.append(row_coords)

        return grid_coords

    def get_cell_image(self, img: np.ndarray, grid_coords: List[List[Tuple]], row: int, col: int) -> np.ndarray:
        if 0 <= row < len(grid_coords) and 0 <= col < len(grid_coords[0]):
            x, y, w, h = grid_coords[row][col]
            return img[y:y+h, x:x+w]
        else:
            raise ValueError(f"Cell coordinates out of range: ({row}, {col})")

    def get_border_region(self, img: np.ndarray, grid_coords: List[List[Tuple]], pos1: Tuple[int, int], pos2: Tuple[int, int]) -> np.ndarray:
        row1, col1 = pos1
        row2, col2 = pos2

        if abs(row1 - row2) + abs(col1 - col2) != 1:
            raise ValueError(f"Cells {pos1} and {pos2} are not adjacent")

        x1, y1, w1, h1 = grid_coords[row1][col1]

        if row1 == row2:
            border_x = x1 + w1 - 10
            border_y = y1
            border_w = 20
            border_h = h1
        else:
            border_x = x1
            border_y = y1 + h1 - 10
            border_w = w1
            border_h = 20

        return img[border_y:border_y+border_h, border_x:border_x+border_w]
