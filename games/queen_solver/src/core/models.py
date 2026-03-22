"""Data models for the Queen Solver system."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class BoardInfo:
    """Information about the detected board."""

    size: int
    image_shape: Tuple[int, int, int]
    horizontal_lines: List[int]
    vertical_lines: List[int]
    cell_height: int
    cell_width: int


@dataclass
class Region:
    """Represents a colored region on the board."""

    id: int
    positions: List[Tuple[int, int]]
    color: np.ndarray
    size: int

    def __post_init__(self):
        self.size = len(self.positions)


@dataclass
class PuzzleState:
    """Complete state of a Queens puzzle."""

    board_info: BoardInfo
    regions: Dict[int, Region]
    solution: Optional[np.ndarray] = None
    is_solvable: bool = True
    validation_errors: List[str] = None

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


@dataclass
class SolverResult:
    """Result of solving a Queens puzzle."""

    success: bool
    solution: Optional[np.ndarray]
    execution_time: float
    iterations: int
    validation_passed: bool
    error_message: Optional[str] = None
