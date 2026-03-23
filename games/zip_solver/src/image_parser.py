from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np


DEFAULT_BOARD_SIZE = 7
OUTER_CONTOUR_THRESHOLD = 180
WALL_PIXEL_THRESHOLD = 75
CLUE_COMPONENT_THRESHOLD = 70

OCR_CANVAS_SIZE = 48
OCR_MIN_SCORE = 0.08
OCR_MAX_VALUE = 50


@dataclass(slots=True)
class _OcrPrediction:
    value: int
    score: float
    candidates: list[tuple[int, float]]


class _ZipClueOcr:
    def __init__(self) -> None:
        self._templates = self._build_templates()

    def predict(self, clue_roi_gray: np.ndarray) -> _OcrPrediction | None:
        normalized = self._normalize_text(clue_roi_gray)
        if normalized is None:
            return None

        scores: list[tuple[int, float]] = []
        for value, templates in self._templates.items():
            score = max(self._best_shift_iou(normalized, template) for template in templates)
            scores.append((value, float(score)))

        scores.sort(key=lambda item: item[1], reverse=True)
        if not scores:
            return None

        best_value, best_score = scores[0]
        if best_score < OCR_MIN_SCORE:
            return None

        return _OcrPrediction(
            value=int(best_value),
            score=float(best_score),
            candidates=[(int(value), float(score)) for value, score in scores[:3]],
        )

    def _build_templates(self) -> dict[int, list[np.ndarray]]:
        fonts = [
            cv2.FONT_HERSHEY_SIMPLEX,
            cv2.FONT_HERSHEY_DUPLEX,
            cv2.FONT_HERSHEY_COMPLEX,
            cv2.FONT_HERSHEY_TRIPLEX,
        ]

        templates: dict[int, list[np.ndarray]] = {}
        for value in range(1, OCR_MAX_VALUE + 1):
            text = str(value)
            rendered: list[np.ndarray] = []

            for font in fonts:
                for scale in (0.55, 0.65, 0.75, 0.85, 0.95, 1.05):
                    for thickness in (1, 2):
                        canvas = np.zeros((OCR_CANVAS_SIZE, OCR_CANVAS_SIZE), dtype=np.uint8)
                        (text_width, text_height), _ = cv2.getTextSize(text, font, scale, thickness)

                        x = (OCR_CANVAS_SIZE - text_width) // 2
                        y = (OCR_CANVAS_SIZE + text_height) // 2 - 1
                        cv2.putText(
                            canvas,
                            text,
                            (x, y),
                            font,
                            scale,
                            (255.0, 255.0, 255.0),
                            thickness,
                            cv2.LINE_AA,
                        )

                        _, binary = cv2.threshold(canvas, 100, 255, cv2.THRESH_BINARY)
                        rendered.append(binary)

            templates[value] = rendered

        return templates

    def _normalize_text(self, clue_roi_gray: np.ndarray) -> np.ndarray | None:
        if clue_roi_gray.size == 0:
            return None

        text_mask = (clue_roi_gray > 160).astype(np.uint8) * 255
        text_mask = cv2.medianBlur(text_mask, 3)

        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(text_mask, connectivity=8)
        if component_count <= 1:
            return None

        keep = np.zeros_like(text_mask)
        height, width = text_mask.shape
        min_area = max(6, (height * width) // 260)

        for label in range(1, component_count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])

            if area < min_area:
                continue

            center_x = x + w / 2
            center_y = y + h / 2
            if abs(center_x - width / 2) > width * 0.45:
                continue
            if abs(center_y - height / 2) > height * 0.45:
                continue

            keep[labels == label] = 255

        if np.count_nonzero(keep) == 0:
            return None

        ys, xs = np.where(keep > 0)
        y1, y2 = int(ys.min()), int(ys.max() + 1)
        x1, x2 = int(xs.min()), int(xs.max() + 1)
        digit = keep[y1:y2, x1:x2]

        side = max(digit.shape[0], digit.shape[1]) + 8
        square = np.zeros((side, side), dtype=np.uint8)
        offset_y = (side - digit.shape[0]) // 2
        offset_x = (side - digit.shape[1]) // 2
        square[offset_y : offset_y + digit.shape[0], offset_x : offset_x + digit.shape[1]] = digit

        normalized = cv2.resize(
            square,
            (OCR_CANVAS_SIZE, OCR_CANVAS_SIZE),
            interpolation=cv2.INTER_NEAREST,
        )
        return normalized

    def _best_shift_iou(self, first: np.ndarray, second: np.ndarray) -> float:
        first_mask = first > 0
        second_mask = second > 0

        best = 0.0
        for shift_y in (-2, -1, 0, 1, 2):
            for shift_x in (-2, -1, 0, 1, 2):
                shifted = np.roll(np.roll(second_mask, shift_y, axis=0), shift_x, axis=1)

                if shift_y > 0:
                    shifted[:shift_y, :] = False
                elif shift_y < 0:
                    shifted[shift_y:, :] = False

                if shift_x > 0:
                    shifted[:, :shift_x] = False
                elif shift_x < 0:
                    shifted[:, shift_x:] = False

                intersection = np.logical_and(first_mask, shifted).sum()
                union = np.logical_or(first_mask, shifted).sum()
                score = float(intersection / union) if union else 0.0
                if score > best:
                    best = score

        return best


@lru_cache(maxsize=1)
def _get_ocr() -> _ZipClueOcr:
    return _ZipClueOcr()


class ZipImageParser:
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
        board_gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)

        x_lines = self._build_grid_lines(board_gray.shape[1], self._board_size)
        y_lines = self._build_grid_lines(board_gray.shape[0], self._board_size)

        blocked_h, blocked_v = self._detect_walls(board_gray, x_lines, y_lines)
        clues, clue_entries = self._detect_clues(board_gray, x_lines, y_lines)

        clue_grid = [[0 for _ in range(self._board_size)] for _ in range(self._board_size)]
        for (row, col), value in clues.items():
            clue_grid[row][col] = int(value)

        return {
            "size": int(self._board_size),
            "blocked_h": blocked_h,
            "blocked_v": blocked_v,
            "clues": clue_entries,
            "clue_grid": clue_grid,
            "board_bbox": bbox,
            "grid_lines": {
                "rows": [int(value) for value in y_lines],
                "cols": [int(value) for value in x_lines],
            },
        }

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
            if bbox_area < image_area * 0.03:
                continue

            aspect_ratio = width / height
            if not (0.72 <= aspect_ratio <= 1.30):
                continue

            fill_ratio = cv2.contourArea(contour) / max(1, bbox_area)
            if fill_ratio < 0.35:
                continue

            contour_center_x = x + width / 2
            contour_center_y = y + height / 2
            center_distance = float(np.hypot(contour_center_x - center_x, contour_center_y - center_y))

            score = (bbox_area * fill_ratio) - (center_distance * 80)
            if score > best_score:
                best_score = score
                best_bbox = (int(x), int(y), int(width), int(height))

        return best_bbox

    def _build_grid_lines(self, axis_length: int, board_size: int) -> list[int]:
        if axis_length <= 1:
            return [0 for _ in range(board_size + 1)]

        lines = np.rint(np.linspace(0, axis_length - 1, board_size + 1)).astype(int)
        return [int(value) for value in lines]

    def _detect_walls(
        self,
        board_gray: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[list[list[bool]], list[list[bool]]]:
        wall_mask = board_gray < WALL_PIXEL_THRESHOLD

        x_steps = np.diff(np.array(x_lines))
        y_steps = np.diff(np.array(y_lines))
        average_cell = float(min(np.mean(x_steps), np.mean(y_steps)))

        pad = max(2, int(round(average_cell * 0.08)))
        probe = max(2, int(round(average_cell * 0.05)))
        ratio_threshold = 0.35

        blocked_h = [[False for _ in range(self._board_size)] for _ in range(self._board_size - 1)]
        blocked_v = [[False for _ in range(self._board_size - 1)] for _ in range(self._board_size)]

        height, width = board_gray.shape

        for row in range(self._board_size - 1):
            boundary_y = y_lines[row + 1]
            for col in range(self._board_size):
                x1 = max(0, x_lines[col] + pad)
                x2 = min(width, x_lines[col + 1] - pad)
                y1 = max(0, boundary_y - probe)
                y2 = min(height, boundary_y + probe + 1)

                patch = wall_mask[y1:y2, x1:x2]
                ratio = float(np.mean(patch)) if patch.size else 0.0
                blocked_h[row][col] = ratio > ratio_threshold

        for row in range(self._board_size):
            for col in range(self._board_size - 1):
                boundary_x = x_lines[col + 1]

                x1 = max(0, boundary_x - probe)
                x2 = min(width, boundary_x + probe + 1)
                y1 = max(0, y_lines[row] + pad)
                y2 = min(height, y_lines[row + 1] - pad)

                patch = wall_mask[y1:y2, x1:x2]
                ratio = float(np.mean(patch)) if patch.size else 0.0
                blocked_v[row][col] = ratio > ratio_threshold

        return blocked_h, blocked_v

    def _detect_clues(
        self,
        board_gray: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[dict[tuple[int, int], int], list[dict[str, Any]]]:
        clue_mask = (board_gray < CLUE_COMPONENT_THRESHOLD).astype(np.uint8) * 255
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(clue_mask, connectivity=8)

        clues: dict[tuple[int, int], int] = {}
        entries_by_cell: dict[tuple[int, int], dict[str, Any]] = {}

        x_steps = np.diff(np.array(x_lines))
        y_steps = np.diff(np.array(y_lines))
        average_cell = float(min(np.mean(x_steps), np.mean(y_steps)))
        cell_area = average_cell * average_cell

        min_area = cell_area * 0.12
        max_area = cell_area * 0.70
        min_side = average_cell * 0.45
        max_side = average_cell * 1.10

        for label in range(1, component_count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            width = int(stats[label, cv2.CC_STAT_WIDTH])
            height = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = float(stats[label, cv2.CC_STAT_AREA])

            if area < min_area or area > max_area:
                continue
            if width < min_side or width > max_side or height < min_side or height > max_side:
                continue

            aspect_ratio = width / max(height, 1)
            if aspect_ratio < 0.7 or aspect_ratio > 1.35:
                continue

            center_x = x + width / 2
            center_y = y + height / 2

            row = self._map_to_cell(center_y, y_lines)
            col = self._map_to_cell(center_x, x_lines)
            if row is None or col is None:
                continue

            roi = board_gray[y : y + height, x : x + width]
            prediction = self._ocr.predict(roi)
            if prediction is None:
                continue

            cell = (row, col)
            current = entries_by_cell.get(cell)
            if current is not None and float(current["confidence"]) >= prediction.score:
                continue

            clues[cell] = int(prediction.value)
            entries_by_cell[cell] = {
                "row": int(row),
                "col": int(col),
                "value": int(prediction.value),
                "confidence": float(prediction.score),
                "candidates": [
                    {
                        "value": int(value),
                        "confidence": float(score),
                    }
                    for value, score in prediction.candidates
                ],
            }

        clue_entries = sorted(entries_by_cell.values(), key=lambda item: int(item["value"]))
        return clues, clue_entries

    def _map_to_cell(self, coordinate: float, lines: list[int]) -> int | None:
        index = int(np.searchsorted(lines, coordinate, side="right") - 1)
        if index < 0 or index >= self._board_size:
            return None
        return index
