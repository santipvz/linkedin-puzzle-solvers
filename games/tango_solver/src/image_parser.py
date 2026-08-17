from typing import List, Tuple, Optional, Dict, Any
import cv2
import numpy as np

from core.commons import BoardBBox, morphological_line_projections, uniform_grid_bounds
from core.vision import build_parsed_board_payload, extract_line_groups, select_regular_line_subset

try:
    from .template_constraint_classifier import TemplateConstraintClassifier
    from .piece_detector import PieceDetector
except ImportError:
    # Fallback for direct execution
    from template_constraint_classifier import TemplateConstraintClassifier
    from piece_detector import PieceDetector


class TangoImageParser:
    """
    Main parser for extracting information from Tango game images.

    Automatically extracts:
    - Fixed pieces placed (moons and circles)
    - Constraints between cells (= and x)
    - Available empty cells
    """

    def __init__(self):
        self.grid_size = 6
        self.piece_detector = PieceDetector()
        self.constraint_classifier = TemplateConstraintClassifier()

    def parse_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            board_img, board_bbox = self._extract_board_crop(img_rgb)

            grid = uniform_grid_bounds(width=board_img.shape[1], height=board_img.shape[0], board_size=self.grid_size)
            grid_coords = [list(row) for row in grid.cells()]

            board_state = self._extract_board_contents(board_img, grid_coords)
            return build_parsed_board_payload(
                board_size=self.grid_size,
                board_bbox=BoardBBox.from_mapping(board_bbox),
                grid=grid,
                extra_fields={**board_state, "grid_coords": grid_coords},
            )

        except Exception as e:
            print(f"Error parsing image: {e}")
            return None

    def _extract_board_crop(self, img: np.ndarray) -> Tuple[np.ndarray, Dict[str, int]]:
        height, width = img.shape[:2]
        bbox = self._detect_board_bbox(img)

        if bbox is None:
            return img, {
                'x': 0,
                'y': 0,
                'width': int(width),
                'height': int(height),
            }

        x, y, crop_width, crop_height = bbox
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(width, int(x + crop_width))
        y2 = min(height, int(y + crop_height))

        if x2 - x1 < 120 or y2 - y1 < 120:
            return img, {
                'x': 0,
                'y': 0,
                'width': int(width),
                'height': int(height),
            }

        return img[y1:y2, x1:x2], {
            'x': int(x1),
            'y': int(y1),
            'width': int(x2 - x1),
            'height': int(y2 - y1),
        }

    def _detect_board_bbox(self, img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        image_height, image_width = gray.shape
        image_area = image_height * image_width

        expected_line_count = self.grid_size + 1
        best_score: Optional[float] = None
        best_bbox: Optional[Tuple[int, int, int, int]] = None

        for block_size in (17, 21):
            if block_size >= min(image_height, image_width):
                continue

            for constant in (3, 4):
                binary = cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    block_size,
                    constant,
                )
                binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

                for frac in (0.1, 0.12, 0.14):
                    horizontal_kernel = max(10, int(image_width * frac))
                    vertical_kernel = max(10, int(image_height * frac))

                    projections = morphological_line_projections(
                        binary,
                        horizontal_kernel_length=horizontal_kernel,
                        vertical_kernel_length=vertical_kernel,
                    )
                    row_groups = extract_line_groups(projections.rows, 255 * max(8, image_width // 9))
                    col_groups = extract_line_groups(projections.cols, 255 * max(8, image_height // 9))

                    subset_options = {
                        "strongest_limit": 14,
                        "min_step": 12,
                        "step_std_penalty": 32,
                        "step_range_penalty": 8,
                    }
                    row_lines, row_score = select_regular_line_subset(row_groups, expected_line_count, **subset_options)
                    col_lines, col_score = select_regular_line_subset(col_groups, expected_line_count, **subset_options)
                    if row_lines is None or col_lines is None:
                        continue

                    row_span = row_lines[-1] - row_lines[0]
                    col_span = col_lines[-1] - col_lines[0]
                    if row_span < 120 or col_span < 120:
                        continue

                    row_step = row_span / self.grid_size
                    col_step = col_span / self.grid_size
                    if row_step < 18 or col_step < 18:
                        continue
                    if abs(row_step - col_step) > max(row_step, col_step) * 0.3:
                        continue

                    board_area = row_span * col_span
                    if board_area < image_area * 0.03:
                        continue

                    square_penalty = abs(row_step - col_step)
                    center_x = (col_lines[0] + col_lines[-1]) / 2
                    center_y = (row_lines[0] + row_lines[-1]) / 2
                    center_distance = float(np.hypot(center_x - (image_width / 2), center_y - (image_height / 2)))

                    touches_edge = (
                        row_lines[0] <= 1
                        or col_lines[0] <= 1
                        or row_lines[-1] >= image_height - 2
                        or col_lines[-1] >= image_width - 2
                    )
                    edge_penalty = 350.0 if touches_edge else 0.0

                    score = (
                        float(row_score or 0.0)
                        + float(col_score or 0.0)
                        + board_area * 0.005
                        - square_penalty * 120
                        - center_distance * 35
                        - edge_penalty
                    )

                    if best_score is None or score > best_score:
                        pad = max(1, int(min(row_step, col_step) * 0.08))
                        x1 = max(0, int(col_lines[0] - pad))
                        y1 = max(0, int(row_lines[0] - pad))
                        x2 = min(image_width, int(col_lines[-1] + pad))
                        y2 = min(image_height, int(row_lines[-1] + pad))
                        if x2 - x1 < 120 or y2 - y1 < 120:
                            continue

                        best_score = score
                        best_bbox = (x1, y1, x2 - x1, y2 - y1)

        return best_bbox

    def _extract_board_contents(self, img: np.ndarray, grid_coords: List[List[Tuple]]) -> Dict[str, Any]:
        board_state = {
            'fixed_pieces': [],
            'constraints': [],
            'empty_cells': []
        }

        for row in range(6):
            for col in range(6):
                x, y, w, h = grid_coords[row][col]
                cell_img = img[y:y+h, x:x+w]

                piece_info = self.piece_detector.detect_piece(cell_img)

                if piece_info['type'] == 'piece':
                    board_state['fixed_pieces'].append({
                        'row': row,
                        'col': col,
                        'piece_type': piece_info['piece_type']
                    })
                else:
                    board_state['empty_cells'].append((row, col))

        constraints = self._detect_edge_constraints(img, grid_coords)
        board_state['constraints'] = constraints

        return board_state

    def _detect_edge_constraints(self, img: np.ndarray, grid_coords: List[List[Tuple]]) -> List[Dict[str, Any]]:
        constraints = []
        height, width = img.shape[:2]

        for row in range(6):
            for col in range(5):
                x1, y1, w1, h1 = grid_coords[row][col]

                border_x = x1 + w1 - 10
                border_y = y1
                border_w = 20
                border_h = h1

                if border_x >= 0 and border_x + border_w < width:
                    border_img = img[border_y:border_y+border_h, border_x:border_x+border_w]
                    constraint_type = self._analyze_border_for_constraint(border_img, is_horizontal=True)

                    if constraint_type:
                        constraints.append({
                            'type': constraint_type,
                            'pos1': (row, col),
                            'pos2': (row, col+1)
                        })

        for row in range(5):
            for col in range(6):
                x1, y1, w1, h1 = grid_coords[row][col]

                border_x = x1
                border_y = y1 + h1 - 10
                border_w = w1
                border_h = 20

                if border_y >= 0 and border_y + border_h < height:
                    border_img = img[border_y:border_y+border_h, border_x:border_x+border_w]
                    constraint_type = self._analyze_border_for_constraint(border_img, is_horizontal=False)

                    if constraint_type:
                        constraints.append({
                            'type': constraint_type,
                            'pos1': (row, col),
                            'pos2': (row+1, col)
                        })

        return constraints

    def _analyze_border_for_constraint(self, border_img: np.ndarray, is_horizontal: bool = True) -> Optional[str]:
        if border_img.size == 0:
            return None

        # Look specifically for constraint color
        target_color = np.array([140, 114, 76])
        color_diff = np.sqrt(np.sum((border_img - target_color) ** 2, axis=2))
        constraint_pixels = np.sum(color_diff < 30)

        if constraint_pixels < 8:
            return None

        constraint_mask = (color_diff < 30).astype(np.uint8) * 255

        if np.sum(constraint_mask > 0) < 5:
            return None

        classification = self.constraint_classifier.classify_constraint(constraint_mask, is_horizontal)

        if classification == 'equals':
            return '='
        elif classification == 'not_equals':
            return 'x'
        else:
            return None
