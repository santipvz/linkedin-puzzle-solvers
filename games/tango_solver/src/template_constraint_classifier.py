import cv2
import numpy as np
from typing import Optional
from pathlib import Path

class TemplateConstraintClassifier:
    """
    Template-based constraint classifier for Tango game.

    Uses template matching with predefined templates to classify constraint symbols
    ('=' for equality, 'x' for difference) found in border regions between board cells.
    """

    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            current_dir = Path(__file__).parent
            templates_dir = current_dir.parent / "templates"

        self.templates_dir = Path(templates_dir)
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        templates = {}

        template_files = {
            'eq_horizontal': 'eq_horizontal_cells.png',
            'eq_vertical': 'eq_vertical_cells.png',
            'x_horizontal': 'x_horizontal_cells.png',
            'x_vertical': 'x_vertical_cells.png'
        }

        for template_name, filename in template_files.items():
            template_path = self.templates_dir / filename
            if template_path.exists():
                template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
                if template is not None:
                    # Extract only the constraint region from the template
                    constraint_region = self._extract_constraint_from_template(template, template_name)
                    if constraint_region is not None:
                        templates[template_name] = constraint_region
                    else:
                        print(f"❌ Failed to extract constraint from template: {template_name}")
                else:
                    print(f"❌ Failed to load template: {template_name}")
            else:
                print(f"❌ Template file not found: {template_path}")

        return templates

    def _extract_constraint_from_template(self, template: np.ndarray, template_name: str) -> Optional[np.ndarray]:
        target_color_bgr = np.array([76, 114, 140])
        color_diff = np.sqrt(np.sum((template - target_color_bgr) ** 2, axis=2))
        constraint_mask = color_diff < 30

        constraint_pixels = np.sum(constraint_mask)

        if constraint_pixels < 10:
            return None

        # Find bounding box of constraint pixels
        rows, cols = np.where(constraint_mask)
        if len(rows) == 0:
            return None

        min_row, max_row = np.min(rows), np.max(rows)
        min_col, max_col = np.min(cols), np.max(cols)

        # Add some padding but keep it reasonable
        padding = 10
        min_row = max(0, min_row - padding)
        max_row = min(template.shape[0] - 1, max_row + padding)
        min_col = max(0, min_col - padding)
        max_col = min(template.shape[1] - 1, max_col + padding)

        # Extract region and convert to grayscale
        constraint_region = template[min_row:max_row+1, min_col:max_col+1]
        constraint_gray = cv2.cvtColor(constraint_region, cv2.COLOR_BGR2GRAY)

        return constraint_gray

    def classify_constraint(self, image: np.ndarray, is_horizontal: bool = True) -> Optional[str]:

        if len(self.templates) == 0:
            return self._fallback_classify(image)

        if len(image.shape) == 3:
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray_image = image.copy()

        processed_image = self._preprocess_image(gray_image)

        # Select appropriate templates based on orientation
        if is_horizontal:
            eq_template_key = 'eq_horizontal'
            x_template_key = 'x_horizontal'
        else:
            eq_template_key = 'eq_vertical'
            x_template_key = 'x_vertical'

        scores = {}

        # Match against equality templates
        if eq_template_key in self.templates:
            eq_score = self._match_template(processed_image, self.templates[eq_template_key])
            scores['equals'] = eq_score

        # Match against difference templates
        if x_template_key in self.templates:
            x_score = self._match_template(processed_image, self.templates[x_template_key])
            scores['not_equals'] = x_score

        if not scores:
            return self._fallback_classify(image)

        # Find best match
        best_type = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_type]

        # Confidence threshold, only return result if confident enough
        min_confidence = 0.1
        if best_score < min_confidence:
            return self._fallback_classify(image)

        # Check if the difference between best and second best is significant
        if len(scores) > 1:
            sorted_scores = sorted(scores.values(), reverse=True)
            if len(sorted_scores) >= 2 and (sorted_scores[0] - sorted_scores[1]) < 0.02:
                # Instead of falling back immediately, be more decisive
                # If both scores are very low, then fallback. Otherwise, take the best.
                if sorted_scores[0] < 0.1:
                    return self._fallback_classify(image)

        return best_type

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        # Apply binary thresholding to get clean binary image
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Invert if most pixels are white (constraint should be black on white)
        if np.sum(binary > 128) > np.sum(binary <= 128):
            binary = 255 - binary

        # Apply morphological operations to clean up noise and strengthen shapes
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Apply dilation to make the shapes slightly thicker for better matching
        kernel2 = np.ones((1, 1), np.uint8)
        dilated = cv2.dilate(cleaned, kernel2, iterations=1)

        return dilated

    def _match_template(self, image: np.ndarray, template: np.ndarray) -> float:

        if image.size == 0 or template.size == 0:
            return 0.0

        # Preprocess template same way as image
        processed_template = self._preprocess_image(template)

        max_score = 0.0

        # Try multiple scales - focusing on smaller scales since templates are larger
        scales = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.75, 1.0]

        for scale in scales:
            # Resize template
            new_width = int(processed_template.shape[1] * scale)
            new_height = int(processed_template.shape[0] * scale)

            if new_width <= 0 or new_height <= 0:
                continue

            if new_width > image.shape[1] * 2 or new_height > image.shape[0] * 2:
                continue

            scaled_template = cv2.resize(processed_template, (new_width, new_height))

            # Skip if template is larger than image
            if scaled_template.shape[0] > image.shape[0] or scaled_template.shape[1] > image.shape[1]:
                continue

            # Template matching
            try:
                result = cv2.matchTemplate(image, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, score, _, _ = cv2.minMaxLoc(result)
                max_score = max(max_score, score)
            except cv2.error:
                continue

        return max_score

    def _fallback_classify(self, image: np.ndarray) -> Optional[str]:
        try:
            from .constraint_classifier import ConstraintClassifier
        except ImportError:
            from constraint_classifier import ConstraintClassifier
        fallback = ConstraintClassifier()
        return fallback.classify_constraint(image)

    def get_constraint_name(self, constraint_type: str) -> str:
        return "equality" if constraint_type == 'equals' else "difference"

    def get_constraint_emoji(self, constraint_type: str) -> str:
        return "🟢" if constraint_type == 'equals' else "🔴"
