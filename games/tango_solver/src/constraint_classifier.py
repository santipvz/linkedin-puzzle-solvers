from typing import Optional
import numpy as np

class ConstraintClassifier:
    """
    Constraint classifier for Tango game.

    Classifies constraint symbols ('=' for equality, 'x' for difference)
    found in border regions between board cells.
    """

    def __init__(self):
        pass

    def classify_constraint(self, image: np.ndarray) -> Optional[str]:
        if len(image.shape) == 3:
            target_color = np.array([140, 114, 76])
            color_diff = np.sqrt(np.sum((image - target_color) ** 2, axis=2))
            mask = (color_diff < 30).astype(np.uint8) * 255
        else:
            mask = image

        h, w = mask.shape

        if h < 3 or w < 3:
            return None

        total_pixels = np.sum(mask > 0)
        if total_pixels < 5:
            return None

        rows, cols = np.where(mask > 0)
        if len(rows) == 0:
            return None

        row_spread = np.std(rows) if len(rows) > 1 else 0
        col_spread = np.std(cols) if len(cols) > 1 else 0

        mid_h, mid_w = h // 2, w // 2

        q1 = np.sum(mask[0:mid_h, 0:mid_w] > 0)          # Top left
        q2 = np.sum(mask[0:mid_h, mid_w:w] > 0)          # Top right
        q3 = np.sum(mask[mid_h:h, 0:mid_w] > 0)          # Bottom left
        q4 = np.sum(mask[mid_h:h, mid_w:w] > 0)          # Bottom right

        quadrants = [q1, q2, q3, q4]
        non_zero_quads = sum(1 for q in quadrants if q > 0)

        # Horizontal vs diagonal connectivity analysis
        horizontal_connectivity = self._count_horizontal_connections(mask)
        diagonal_connectivity = self._count_diagonal_connections(mask)

        # Bounding box shape analysis
        min_row, max_row = np.min(rows), np.max(rows)
        min_col, max_col = np.min(cols), np.max(cols)

        bbox_width = max_col - min_col + 1
        bbox_height = max_row - min_row + 1
        bbox_aspect = bbox_width / bbox_height if bbox_height > 0 else 1

        cross_pattern_score = 0
        equal_pattern_score = 0

        # Criterion 1: Quadrant distribution
        # For 'x': expect pixels in opposite quadrants (1&4 or 2&3)
        if q1 > 0 and q4 > 0:  # Main diagonal
            cross_pattern_score += 2
        if q2 > 0 and q3 > 0:  # Secondary diagonal
            cross_pattern_score += 2
        if non_zero_quads >= 3:  # Wide distribution
            cross_pattern_score += 1

        # For '=': expect horizontally concentrated pixels
        if q1 > 0 and q2 > 0:  # Top line
            equal_pattern_score += 2
        if q3 > 0 and q4 > 0:  # Bottom line
            equal_pattern_score += 2
        if (q1 + q2) > 0 and (q3 + q4) > 0:  # Both lines
            equal_pattern_score += 3

        # Criterion 2: Connectivity
        diagonal_ratio = diagonal_connectivity / max(horizontal_connectivity, 1)
        horizontal_ratio = horizontal_connectivity / max(diagonal_connectivity, 1)

        if diagonal_connectivity > horizontal_connectivity:
            cross_pattern_score += 2
            # Bonus for strong diagonal dominance
            if diagonal_ratio >= 1.5:
                cross_pattern_score += 2
        elif horizontal_connectivity > diagonal_connectivity:
            equal_pattern_score += 2
            # Bonus for strong horizontal dominance
            if horizontal_ratio >= 1.5:
                equal_pattern_score += 2

        # Criterion 3: Bounding box aspect
        if bbox_aspect > 1.5:
            equal_pattern_score += 3
        elif 0.7 <= bbox_aspect <= 1.3:
            cross_pattern_score += 2

        # Criterion 4: Spatial dispersion
        if row_spread > col_spread and row_spread > 3:
            equal_pattern_score += 1
        elif col_spread > row_spread and col_spread > 3:
            equal_pattern_score += 1
        elif abs(row_spread - col_spread) < 2:
            cross_pattern_score += 1

        # Final decision
        if cross_pattern_score > equal_pattern_score:
            return 'not_equals'
        elif equal_pattern_score > cross_pattern_score:
            return 'equals'
        else:
            if bbox_aspect > 1.5:
                return 'equals'
            else:
                return 'not_equals'

    def _count_horizontal_connections(self, mask: np.ndarray) -> int:
        h, w = mask.shape
        connections = 0

        for r in range(h):
            for c in range(w-1):
                if mask[r, c] > 0 and mask[r, c+1] > 0:
                    connections += 1

        return connections

    def _count_diagonal_connections(self, mask: np.ndarray) -> int:
        h, w = mask.shape
        connections = 0

        for r in range(h-1):
            for c in range(w-1):
                if mask[r, c] > 0 and mask[r+1, c+1] > 0:
                    connections += 1
                if mask[r, c+1] > 0 and mask[r+1, c] > 0:
                    connections += 1

        return connections

    def get_constraint_name(self, constraint_type: str) -> str:
        return "equality" if constraint_type == '=' else "difference"

    def get_constraint_emoji(self, constraint_type: str) -> str:
        return "🟢" if constraint_type == '=' else "🔴"
