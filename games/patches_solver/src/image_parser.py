from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import itertools
from math import isqrt
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.neighbors import KNeighborsClassifier


DEFAULT_BOARD_SIZE = 6
OUTER_CONTOUR_THRESHOLD = 242
CLUE_SATURATION_THRESHOLD = 34

DIGIT_CANVAS_SIZE = 28
OCR_MIN_SCORE = 0.34

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


@dataclass(slots=True)
class _OcrPrediction:
    value: int
    score: float
    candidates: list[tuple[int, float]]


@dataclass(slots=True)
class _DigitChoice:
    digit: int
    score: float


class _PatchesClueOcr:
    def __init__(self) -> None:
        self._classifier = self._build_classifier()

    def predict(self, clue_roi_bgr: np.ndarray, max_value: int | None = None) -> _OcrPrediction | None:
        digit_options = self._extract_digit_options(clue_roi_bgr)
        if not digit_options:
            return None

        ranked_candidates: list[tuple[int, float]] = []
        for combo in itertools.product(*digit_options):
            if not combo:
                continue

            if len(combo) > 1 and combo[0].digit == 0:
                continue

            value = int("".join(str(choice.digit) for choice in combo))
            if value <= 0:
                continue
            if max_value is not None and value > max_value:
                continue

            score = float(sum(choice.score for choice in combo) / len(combo))
            ranked_candidates.append((value, score))

        if not ranked_candidates:
            return None

        deduped: dict[int, float] = {}
        for value, score in ranked_candidates:
            previous = deduped.get(value)
            if previous is None or score > previous:
                deduped[value] = score

        final_candidates = sorted(deduped.items(), key=lambda item: item[1], reverse=True)
        best_value, best_score = final_candidates[0]
        if best_score < OCR_MIN_SCORE:
            return None

        return _OcrPrediction(
            value=int(best_value),
            score=float(best_score),
            candidates=[(int(value), float(score)) for value, score in final_candidates[:3]],
        )

    def _extract_digit_options(self, clue_roi_bgr: np.ndarray) -> list[list[_DigitChoice]]:
        if clue_roi_bgr.size == 0:
            return []

        hsv = cv2.cvtColor(clue_roi_bgr, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        text_mask = ((saturation < 100) & (value > 152)).astype(np.uint8) * 255
        if np.count_nonzero(text_mask) < 12:
            return []

        text_mask = cv2.medianBlur(text_mask, 3)
        kernel = np.ones((2, 2), dtype=np.uint8)
        text_mask = cv2.morphologyEx(text_mask, cv2.MORPH_OPEN, kernel)

        component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(text_mask, connectivity=8)
        if component_count <= 1:
            return []

        roi_height, roi_width = text_mask.shape
        min_area = max(14, int(round((roi_height * roi_width) * 0.007)))
        boxes: list[dict[str, int]] = []

        for label in range(1, component_count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            width = int(stats[label, cv2.CC_STAT_WIDTH])
            height = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])
            center_x, center_y = centroids[label]

            if area < min_area or width < 2 or height < 4:
                continue
            if width > int(round(roi_width * 0.72)) or height > int(round(roi_height * 0.82)):
                continue
            if x <= int(round(roi_width * 0.03)) or y <= int(round(roi_height * 0.03)):
                continue
            if (x + width) >= int(round(roi_width * 0.97)) or (y + height) >= int(round(roi_height * 0.97)):
                continue
            if center_x < roi_width * 0.07 or center_x > roi_width * 0.93:
                continue
            if center_y < roi_height * 0.08 or center_y > roi_height * 0.9:
                continue

            boxes.append(
                {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "area": area,
                }
            )

        if not boxes:
            return []

        boxes.sort(key=lambda box: box["x"])
        merged_boxes: list[dict[str, int]] = []

        for box in boxes:
            if not merged_boxes:
                merged_boxes.append(box)
                continue

            previous = merged_boxes[-1]
            prev_right = previous["x"] + previous["width"]
            gap = box["x"] - prev_right
            vertically_aligned = abs((box["y"] + box["height"] // 2) - (previous["y"] + previous["height"] // 2)) <= max(
                3,
                int(round(min(previous["height"], box["height"]) * 0.55)),
            )

            if gap <= 2 and vertically_aligned:
                x1 = min(previous["x"], box["x"])
                y1 = min(previous["y"], box["y"])
                x2 = max(previous["x"] + previous["width"], box["x"] + box["width"])
                y2 = max(previous["y"] + previous["height"], box["y"] + box["height"])
                previous["x"] = x1
                previous["y"] = y1
                previous["width"] = x2 - x1
                previous["height"] = y2 - y1
                previous["area"] += box["area"]
            else:
                merged_boxes.append(box)

        if len(merged_boxes) > 2:
            merged_boxes = sorted(merged_boxes, key=lambda box: box["area"], reverse=True)[:2]
            merged_boxes.sort(key=lambda box: box["x"])

        options: list[list[_DigitChoice]] = []
        classes = self._classifier.classes_

        for box in merged_boxes:
            x = box["x"]
            y = box["y"]
            width = box["width"]
            height = box["height"]

            digit_mask = text_mask[y : y + height, x : x + width]
            normalized = self._normalize_digit(digit_mask)
            if normalized is None:
                continue

            features = normalized.flatten().astype(np.float32)
            probabilities = self._classifier.predict_proba([features])[0]
            top_indexes = np.argsort(probabilities)[::-1][:3]

            choices = [
                _DigitChoice(digit=int(classes[index]), score=float(probabilities[index]))
                for index in top_indexes
            ]
            options.append(choices)

        return options

    def _normalize_digit(self, digit_mask: np.ndarray) -> np.ndarray | None:
        if digit_mask.size == 0:
            return None

        binary = (digit_mask > 0).astype(np.uint8)
        if np.count_nonzero(binary) < 6:
            return None

        ys, xs = np.where(binary > 0)
        y1, y2 = int(ys.min()), int(ys.max() + 1)
        x1, x2 = int(xs.min()), int(xs.max() + 1)
        crop = binary[y1:y2, x1:x2]

        side = max(crop.shape[0], crop.shape[1]) + 8
        square = np.zeros((side, side), dtype=np.uint8)
        offset_y = (side - crop.shape[0]) // 2
        offset_x = (side - crop.shape[1]) // 2
        square[offset_y : offset_y + crop.shape[0], offset_x : offset_x + crop.shape[1]] = crop

        normalized = cv2.resize(
            square,
            (DIGIT_CANVAS_SIZE, DIGIT_CANVAS_SIZE),
            interpolation=cv2.INTER_NEAREST,
        )

        return normalized

    def _build_classifier(self) -> KNeighborsClassifier:
        font_paths = [path for path in FONT_CANDIDATES if Path(path).exists()]
        if not font_paths:
            raise RuntimeError("Could not find any system font for patches OCR templates.")

        features: list[np.ndarray] = []
        labels: list[int] = []

        for digit in range(10):
            text = str(digit)
            for font_path in font_paths:
                for font_size in (14, 16, 18, 20, 22, 24):
                    for stroke_width in (0, 1, 2):
                        for dx in (-2, -1, 0, 1, 2):
                            for dy in (-2, -1, 0, 1, 2):
                                bitmap = self._render_digit_template(
                                    text=text,
                                    font_path=font_path,
                                    font_size=font_size,
                                    stroke_width=stroke_width,
                                    dx=dx,
                                    dy=dy,
                                )
                                features.append(bitmap.flatten().astype(np.float32))
                                labels.append(int(digit))

        classifier = KNeighborsClassifier(n_neighbors=3, weights="distance")
        classifier.fit(np.array(features), np.array(labels))
        return classifier

    def _render_digit_template(
        self,
        text: str,
        font_path: str,
        font_size: int,
        stroke_width: int,
        dx: int,
        dy: int,
    ) -> np.ndarray:
        image = Image.new("L", (DIGIT_CANVAS_SIZE, DIGIT_CANVAS_SIZE), 0)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(font_path, size=font_size)

        left, top, right, bottom = draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=stroke_width,
        )
        width = right - left
        height = bottom - top

        x = ((DIGIT_CANVAS_SIZE - width) // 2) - left + dx
        y = ((DIGIT_CANVAS_SIZE - height) // 2) - top + dy

        draw.text(
            (x, y),
            text,
            fill=255,
            font=font,
            stroke_width=stroke_width,
            stroke_fill=255,
        )

        template = (np.array(image, dtype=np.uint8) > 84).astype(np.uint8)
        return template


@lru_cache(maxsize=1)
def _get_ocr() -> _PatchesClueOcr:
    return _PatchesClueOcr()


class PatchesImageParser:
    def __init__(self, board_size: int = DEFAULT_BOARD_SIZE) -> None:
        self._board_size = int(board_size)
        self._ocr = _get_ocr()

    @property
    def board_size(self) -> int:
        return self._board_size

    def parse_image(self, image_path: str | Path) -> dict[str, Any]:
        path = Path(image_path)
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not load image: {path}")

        board_crop, bbox = self._extract_board_crop(image)

        board_size = self._board_size
        row_lines = self._build_grid_lines(board_crop.shape[0], board_size)
        col_lines = self._build_grid_lines(board_crop.shape[1], board_size)
        clues = self._detect_clues(board_crop, row_lines, col_lines)

        clue_grid = [[None for _ in range(board_size)] for _ in range(board_size)]
        for clue in clues:
            clue_grid[int(clue["row"])][int(clue["col"])] = clue["value"]

        return {
            "board_size": int(board_size),
            "clues": clues,
            "clue_grid": clue_grid,
            "board_bbox": bbox,
            "grid_lines": {
                "rows": [int(value) for value in row_lines],
                "cols": [int(value) for value in col_lines],
            },
        }

    def _detect_clues(self, board_bgr: np.ndarray, row_lines: list[int], col_lines: list[int]) -> list[dict[str, Any]]:
        clues: list[dict[str, Any]] = []
        board_hsv = cv2.cvtColor(board_bgr, cv2.COLOR_BGR2HSV)

        board_size = self._board_size
        for row in range(board_size):
            for col in range(board_size):
                y1 = row_lines[row]
                y2 = row_lines[row + 1]
                x1 = col_lines[col]
                x2 = col_lines[col + 1]
                if y2 <= y1 or x2 <= x1:
                    continue

                cell_hsv = board_hsv[y1:y2, x1:x2]
                if cell_hsv.size == 0:
                    continue

                if not self._is_colored_clue_cell(cell_hsv):
                    continue

                badge = self._extract_badge_component(cell_hsv)
                if badge is None:
                    badge = {
                        "x": float(max(0, (cell_hsv.shape[1] // 2) - max(8, cell_hsv.shape[1] // 4))),
                        "y": float(max(0, (cell_hsv.shape[0] // 2) - max(8, cell_hsv.shape[0] // 4))),
                        "width": float(max(10, cell_hsv.shape[1] // 2)),
                        "height": float(max(10, cell_hsv.shape[0] // 2)),
                        "fill_ratio": 0.0,
                    }

                ratio = float(badge["width"]) / max(1, float(badge["height"]))
                shape = self._classify_shape(ratio)

                bx = int(badge["x"])
                by = int(badge["y"])
                bw = int(badge["width"])
                bh = int(badge["height"])

                roi = board_bgr[y1 + by : y1 + by + bh, x1 + bx : x1 + bx + bw]
                prediction = self._ocr.predict(roi, max_value=self._board_size * self._board_size)
                clue_value = int(prediction.value) if prediction is not None else None

                if shape == "square" and clue_value is not None:
                    side = isqrt(clue_value)
                    if side * side != clue_value:
                        shape = "any"

                clues.append(
                    {
                        "row": int(row),
                        "col": int(col),
                        "shape": shape,
                        "value": clue_value,
                        "confidence": float(prediction.score) if prediction is not None else 0.0,
                        "candidates": [
                            {"value": int(value), "confidence": float(score)}
                            for value, score in (prediction.candidates if prediction is not None else [])
                        ],
                        "badge_ratio": float(ratio),
                        "badge_fill": float(badge["fill_ratio"]),
                    }
                )

        clues.sort(key=lambda clue: (int(clue["row"]), int(clue["col"])))
        return clues

    def _is_colored_clue_cell(self, cell_hsv: np.ndarray) -> bool:
        if cell_hsv.size == 0:
            return False

        cell_height, cell_width = cell_hsv.shape[:2]
        pad_y = max(1, int(round(cell_height * 0.12)))
        pad_x = max(1, int(round(cell_width * 0.12)))
        inner = cell_hsv[pad_y : max(pad_y + 1, cell_height - pad_y), pad_x : max(pad_x + 1, cell_width - pad_x)]

        if inner.size == 0:
            return False

        saturation = inner[:, :, 1]
        return float(np.percentile(saturation, 92)) >= CLUE_SATURATION_THRESHOLD

    def _extract_badge_component(self, cell_hsv: np.ndarray) -> dict[str, float] | None:
        saturation = cell_hsv[:, :, 1]
        value = cell_hsv[:, :, 2]
        threshold = max(48.0, float(np.percentile(saturation, 79)))
        mask = ((saturation >= threshold) & (value > 48)).astype(np.uint8) * 255

        kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        del labels
        if component_count <= 1:
            return None

        cell_height, cell_width = saturation.shape
        min_area = max(90, int(round((cell_height * cell_width) * 0.03)))
        max_center_distance = max(cell_height, cell_width) * 0.45

        best: tuple[float, int] | None = None
        for label in range(1, component_count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            width = int(stats[label, cv2.CC_STAT_WIDTH])
            height = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])

            if area < min_area or width < 8 or height < 8:
                continue

            center_x, center_y = centroids[label]
            center_distance = float(np.hypot(center_x - (cell_width / 2), center_y - (cell_height / 2)))
            if center_distance > max_center_distance:
                continue

            score = float(area) - center_distance * 1.7
            if best is None or score > best[0]:
                best = (score, label)

        if best is None:
            return None

        chosen_label = int(best[1])
        x = int(stats[chosen_label, cv2.CC_STAT_LEFT])
        y = int(stats[chosen_label, cv2.CC_STAT_TOP])
        width = int(stats[chosen_label, cv2.CC_STAT_WIDTH])
        height = int(stats[chosen_label, cv2.CC_STAT_HEIGHT])
        area = int(stats[chosen_label, cv2.CC_STAT_AREA])
        fill_ratio = float(area / max(1, width * height))

        return {
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "fill_ratio": fill_ratio,
        }

    def _classify_shape(self, ratio: float) -> str:
        if ratio >= 1.30:
            return "wide"
        if ratio <= 0.78:
            return "tall"
        if 0.92 <= ratio <= 1.05:
            return "square"
        return "any"

    def _extract_board_crop(self, image: np.ndarray) -> tuple[np.ndarray, dict[str, int]]:
        image_height, image_width = image.shape[:2]
        bbox = self._detect_board_bbox(image)

        if bbox is None:
            return image, {
                "x": 0,
                "y": 0,
                "width": int(image_width),
                "height": int(image_height),
            }

        x, y, width, height = bbox
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(image_width, x + width)
        y2 = min(image_height, y + height)

        crop = image[y1:y2, x1:x2]
        metadata = {
            "x": int(x1),
            "y": int(y1),
            "width": int(x2 - x1),
            "height": int(y2 - y1),
        }
        return crop, metadata

    def _detect_board_bbox(self, image: np.ndarray) -> tuple[int, int, int, int] | None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = (gray < OUTER_CONTOUR_THRESHOLD).astype(np.uint8) * 255

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        image_height, image_width = gray.shape
        image_area = image_height * image_width
        center_x = image_width / 2
        center_y = image_height / 2

        best_score = float("-inf")
        best_bbox: tuple[int, int, int, int] | None = None

        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if width <= 0 or height <= 0:
                continue

            bbox_area = width * height
            if bbox_area < image_area * 0.04:
                continue

            aspect_ratio = width / max(1, height)
            if not (0.80 <= aspect_ratio <= 1.22):
                continue

            fill_ratio = cv2.contourArea(contour) / max(1, bbox_area)
            if fill_ratio < 0.30:
                continue

            contour_center_x = x + width / 2
            contour_center_y = y + height / 2
            center_distance = float(np.hypot(contour_center_x - center_x, contour_center_y - center_y))

            score = (bbox_area * fill_ratio) - (center_distance * 90)
            if score > best_score:
                best_score = score
                best_bbox = (int(x), int(y), int(width), int(height))

        return best_bbox

    def _build_grid_lines(self, axis_length: int, board_size: int) -> list[int]:
        if axis_length <= 1:
            return [0 for _ in range(board_size + 1)]

        lines = np.rint(np.linspace(0, axis_length, board_size + 1)).astype(int)
        lines[0] = 0
        lines[-1] = axis_length
        return [int(value) for value in lines]
