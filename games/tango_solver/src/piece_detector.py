from typing import Dict, Any
import cv2
import numpy as np


class PieceDetector:
    def __init__(self):
        pass

    def detect_piece(self, cell_img: np.ndarray) -> Dict[str, Any]:

        hsv = cv2.cvtColor(cell_img, cv2.COLOR_RGB2HSV)

        avg_color = np.mean(cell_img.reshape(-1, 3), axis=0)

        blue_score = self._detect_blue_by_rgb(avg_color)
        orange_score = self._detect_orange_by_rgb(avg_color)

        # Color ranges for HSV detection
        blue_ranges = [
            ([100, 50, 50], [130, 255, 255]),    # Standard blue
            ([200, 150, 150], [230, 255, 255]),  # Specific range for moon interior
            ([210, 180, 120], [240, 255, 200]),  # Specific range for moon outline
            ([195, 100, 100], [245, 255, 255]),  # Wide range for moon variations
        ]

        orange_ranges = [
            ([10, 100, 100], [25, 255, 255]),    # Standard orange
            ([254, 169, 27], [254, 169, 27]),    # Specific range for circle interior
            ([193, 99, 32], [193, 99, 32]),      # Specific range for circle outline
            ([5, 100, 100], [15, 255, 255]),     # Wide range for circle variations
        ]

        blue_pixels = 0
        orange_pixels = 0

        for blue_lower, blue_upper in blue_ranges:
            blue_mask = cv2.inRange(hsv, np.array(blue_lower), np.array(blue_upper))
            blue_pixels = max(blue_pixels, cv2.countNonZero(blue_mask))

        for orange_lower, orange_upper in orange_ranges:
            orange_mask = cv2.inRange(hsv, np.array(orange_lower), np.array(orange_upper))
            orange_pixels = max(orange_pixels, cv2.countNonZero(orange_mask))

        min_pixels = cell_img.shape[0] * cell_img.shape[1] * 0.05

        total_blue_score = blue_pixels + blue_score * 10
        total_orange_score = orange_pixels + orange_score * 10

        if total_blue_score > min_pixels and total_blue_score > total_orange_score:
            return {'type': 'piece', 'piece_type': 0}  # Moon
        elif total_orange_score > min_pixels and total_orange_score > total_blue_score:
            return {'type': 'piece', 'piece_type': 1}  # Circle

        return {'type': 'empty'}

    def _detect_blue_by_rgb(self, avg_color: np.ndarray) -> float:
        r, g, b = avg_color

        if b > 100 and r < 150 and b > r and b > g:
            blue_score = (2 * b) - (r + g)
            return max(0, blue_score)
        return 0

    def _detect_orange_by_rgb(self, avg_color: np.ndarray) -> float:
        r, g, b = avg_color

        if r > 150 and g > 100 and b < 100 and r > b and g > b:
            orange_score = (r + g) - (2 * b)
            return max(0, orange_score)
        return 0

    def get_piece_name(self, piece_type: int) -> str:
        return "MOON" if piece_type == 0 else "CIRCLE"

    def get_piece_emoji(self, piece_type: int) -> str:
        return "🌙" if piece_type == 0 else "🟠"
