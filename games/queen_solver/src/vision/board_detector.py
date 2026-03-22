"""Advanced board detection using edge detection for reliable grid detection."""

from typing import List, Tuple

import cv2
import numpy as np

from src.core.interfaces import BoardDetector


class EdgeDetectionBoardDetector(BoardDetector):
    """Board detector using edge detection for reliable grid identification."""

    def __init__(self):
        self.common_sizes = [6, 7, 8, 9, 10, 11, 12]

    def detect_board_size(self, image: np.ndarray) -> int:
        """Detect board size using edge detection (most reliable method)."""
        # Use edge detection to get both dimensions
        h_size, v_size = self._detect_board_dimensions(image)

        print(f"🔍 Board dimensions detected: {h_size}x{v_size} (rows x cols)")

        # For Queens puzzle, we need square boards
        if h_size != v_size:
            print(f"⚠️  WARNING: Non-square board detected ({h_size}x{v_size})")
            print("   Queens puzzle requires square boards - this board cannot have a valid solution")
            # Return 0 to indicate invalid board for Queens puzzle
            return 0

        # Validate result is reasonable for square boards
        if 6 <= h_size <= 12:
            return h_size

        # Fallback to basic validation if edge detection fails
        return self._detect_size_basic_fallback(image)

    def detect_grid(self, image: np.ndarray, board_size: int) -> Tuple[List[int], List[int]]:
        """Create uniform grid based on detected board size."""
        height, width = image.shape[:2]

        # Calculate ideal cell size
        cell_height = height // board_size
        cell_width = width // board_size

        # Create equidistant lines
        h_lines = [i * cell_height for i in range(board_size + 1)]
        v_lines = [i * cell_width for i in range(board_size + 1)]

        # Adjust final lines to exact image edges
        h_lines[-1] = height - 1
        v_lines[-1] = width - 1

        return h_lines, v_lines

    def _detect_board_dimensions(self, image: np.ndarray) -> Tuple[int, int]:
        """Detect board dimensions (rows, cols) separately using edge detection."""
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Enhance for edge detection
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100, apertureSize=3)

        # Morphological operations
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # Detect lines conservatively
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=int(min(height, width) * 0.4))

        if lines is None:
            return 0, 0

        # Extract and filter lines
        h_lines, v_lines = self._extract_and_filter_lines(lines, height, width)

        h_size = len(h_lines) - 1 if len(h_lines) > 1 else 0
        v_size = len(v_lines) - 1 if len(v_lines) > 1 else 0

        return h_size, v_size

    def _detect_size_by_improved_edges(self, image: np.ndarray) -> int:
        """Detect size using improved edge analysis."""
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Enhance for edge detection
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100, apertureSize=3)

        # Morphological operations
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # Detect lines conservatively
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=int(min(height, width) * 0.4))

        if lines is None:
            return 0

        # Extract and filter lines
        h_lines, v_lines = self._extract_and_filter_lines(lines, height, width)

        h_size = len(h_lines) - 1 if len(h_lines) > 1 else 0
        v_size = len(v_lines) - 1 if len(v_lines) > 1 else 0

        if abs(h_size - v_size) <= 1 and h_size > 0 and v_size > 0:
            return max(h_size, v_size)

        return 0

    def _detect_size_basic_fallback(self, image: np.ndarray) -> int:
        """Fallback method testing common sizes."""
        for size in self.common_sizes:
            if self._validate_size_against_image(image, size):
                return size
        return 9  # Default fallback

    def _extract_and_filter_lines(self, lines: np.ndarray, height: int, width: int) -> Tuple[List[int], List[int]]:
        """Extract and filter horizontal and vertical lines."""
        h_positions = []
        v_positions = []

        for line in lines:
            rho, theta = line[0]

            # Classify lines with strict tolerance
            if abs(theta) < np.pi/8 or abs(theta - np.pi) < np.pi/8:
                # Vertical line
                x = int(rho / np.cos(theta)) if abs(np.cos(theta)) > 0.1 else int(rho)
                if 10 <= x <= width - 10:
                    v_positions.append(x)
            elif abs(theta - np.pi/2) < np.pi/8:
                # Horizontal line
                y = int(rho / np.sin(theta)) if abs(np.sin(theta)) > 0.1 else int(rho)
                if 10 <= y <= height - 10:
                    h_positions.append(y)

        # Filter close lines
        h_filtered = self._filter_close_lines(h_positions, height // 15)
        v_filtered = self._filter_close_lines(v_positions, width // 15)

        # Add borders if needed
        if h_filtered and h_filtered[0] > 20:
            h_filtered.insert(0, 0)
        if h_filtered and h_filtered[-1] < height - 20:
            h_filtered.append(height - 1)

        if v_filtered and v_filtered[0] > 20:
            v_filtered.insert(0, 0)
        if v_filtered and v_filtered[-1] < width - 20:
            v_filtered.append(width - 1)

        return h_filtered, v_filtered

    def _filter_close_lines(self, positions: List[int], min_distance: int) -> List[int]:
        """Filter lines that are too close to each other."""
        if not positions:
            return []

        positions = sorted(list(set(positions)))
        filtered = [positions[0]]

        for pos in positions[1:]:
            if pos - filtered[-1] >= min_distance:
                filtered.append(pos)

        return filtered

    def _validate_size_against_image(self, image: np.ndarray, size: int) -> bool:
        """Validate if a size makes sense for the image."""
        height, width = image.shape[:2]

        cell_height = height // size
        cell_width = width // size

        # Check reasonable ranges
        if not (25 <= cell_height <= 150) or not (25 <= cell_width <= 150):
            return False

        # Check aspect ratio
        aspect_ratio = cell_width / cell_height
        return 0.7 <= aspect_ratio <= 1.3
