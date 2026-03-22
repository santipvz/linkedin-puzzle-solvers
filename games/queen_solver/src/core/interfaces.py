"""Base interfaces and abstract classes for the Queen Solver system."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import numpy as np


class BoardDetector(ABC):
    """Abstract base class for board detection algorithms."""

    @abstractmethod
    def detect_board_size(self, image: np.ndarray) -> int:
        """Detect the size of the board (n for nxn board).

        Args:
            image: Input image containing the board

        Returns:
            Size of the board

        """

    @abstractmethod
    def detect_grid(self, image: np.ndarray, board_size: int) -> Tuple[List[int], List[int]]:
        """Detect the grid lines in the image.

        Args:
            image: Input image
            board_size: Size of the board

        Returns:
            Tuple of (horizontal_lines, vertical_lines)

        """


class RegionExtractor(ABC):
    """Abstract base class for region extraction algorithms."""

    @abstractmethod
    def extract_regions(self, image: np.ndarray, grid_lines: Tuple[List[int], List[int]],
                       board_size: int) -> Dict[int, List[Tuple[int, int]]]:
        """Extract colored regions from the board.

        Args:
            image: Input image
            grid_lines: Horizontal and vertical grid lines
            board_size: Size of the board

        Returns:
            Dictionary mapping region_id to list of (row, col) positions

        """


class PuzzleSolver(ABC):
    """Abstract base class for puzzle solving algorithms."""

    @abstractmethod
    def solve(self, board_size: int, regions: Dict[int, List[Tuple[int, int]]]) -> Optional[np.ndarray]:
        """Solve the Queens puzzle.

        Args:
            board_size: Size of the board
            regions: Dictionary of regions

        Returns:
            Solution matrix or None if no solution exists

        """


class SolutionValidator(ABC):
    """Abstract base class for solution validation."""

    @abstractmethod
    def validate(self, solution: np.ndarray, regions: Dict[int, List[Tuple[int, int]]]) -> bool:
        """Validate a solution.

        Args:
            solution: Solution matrix
            regions: Dictionary of regions

        Returns:
            True if solution is valid, False otherwise

        """


class ResultVisualizer(ABC):
    """Abstract base class for result visualization."""

    @abstractmethod
    def visualize(self, original_image: np.ndarray, solution: Optional[np.ndarray],
                 grid_lines: Tuple[List[int], List[int]],
                 regions: Dict[int, List[Tuple[int, int]]]) -> np.ndarray:
        """Create visualization of the solution.

        Args:
            original_image: Original input image
            solution: Solution matrix (can be None)
            grid_lines: Grid lines
            regions: Regions dictionary

        Returns:
            Visualization image

        """
