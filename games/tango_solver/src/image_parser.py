from typing import List, Tuple, Optional, Dict, Any
import cv2
import numpy as np

try:
    from .template_constraint_classifier import TemplateConstraintClassifier
    from .grid_detector import GridDetector
    from .piece_detector import PieceDetector
except ImportError:
    # Fallback for direct execution
    from template_constraint_classifier import TemplateConstraintClassifier
    from grid_detector import GridDetector
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
        self.grid_detector = GridDetector()
        self.piece_detector = PieceDetector()
        self.constraint_classifier = TemplateConstraintClassifier()

    def parse_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            grid_coords = self.grid_detector.detect_grid(img_rgb)

            board_state = self._extract_board_contents(img_rgb, grid_coords)

            board_state['grid_coords'] = grid_coords

            return board_state

        except Exception as e:
            print(f"Error parsing image: {e}")
            return None

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
