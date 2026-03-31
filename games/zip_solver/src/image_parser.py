from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np


DEFAULT_BOARD_SIZE = 7
AUTO_BOARD_SIZES = (6, 7)
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

    def predict(self, clue_roi_gray: np.ndarray, max_value: int | None = None) -> _OcrPrediction | None:
        normalized = self._normalize_text(clue_roi_gray)
        if normalized is None:
            return None

        scores: list[tuple[int, float]] = []
        for value, templates in self._templates.items():
            if max_value is not None and value > max_value:
                continue
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
        first_u8 = np.where(first > 0, 255, 0).astype(np.uint8)
        second_u8 = np.where(second > 0, 255, 0).astype(np.uint8)

        padded = cv2.copyMakeBorder(second_u8, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
        response = cv2.matchTemplate(padded, first_u8, cv2.TM_CCORR_NORMED)
        if response.size == 0:
            return 0.0

        return float(np.max(response))


@lru_cache(maxsize=1)
def _get_ocr() -> _ZipClueOcr:
    return _ZipClueOcr()


class ZipImageParser:
    def __init__(self, board_size: int | None = None) -> None:
        self._board_size = int(board_size) if board_size is not None else None
        self._ocr = _get_ocr()

    @property
    def board_size(self) -> int | None:
        return self._board_size

    def parse_image(self, image_path: str | Path) -> dict[str, Any]:
        path = Path(image_path)
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not load image: {path}")

        board_crop, bbox = self._extract_board_crop(image)
        board_gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)

        if self._board_size is not None:
            board_size = self._board_size
            x_lines = self._build_grid_lines(board_gray.shape[1], board_size)
            y_lines = self._build_grid_lines(board_gray.shape[0], board_size)
            clues, clue_entries, clue_component_mask, _ = self._detect_clues(
                board_gray,
                x_lines,
                y_lines,
                board_size=board_size,
            )
        else:
            (
                board_size,
                x_lines,
                y_lines,
                clues,
                clue_entries,
                clue_component_mask,
            ) = self._detect_board_layout(board_gray)
        blocked_h, blocked_v = self._detect_walls(
            board_gray,
            x_lines,
            y_lines,
            board_size=board_size,
            clue_component_mask=clue_component_mask,
        )

        clue_grid = [[0 for _ in range(board_size)] for _ in range(board_size)]
        for (row, col), value in clues.items():
            clue_grid[row][col] = int(value)

        return {
            "size": int(board_size),
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

    def _detect_board_layout(
        self,
        board_gray: np.ndarray,
    ) -> tuple[
        int,
        list[int],
        list[int],
        dict[tuple[int, int], int],
        list[dict[str, Any]],
        np.ndarray,
    ]:
        best_size = DEFAULT_BOARD_SIZE
        best_x_lines = self._build_grid_lines(board_gray.shape[1], best_size)
        best_y_lines = self._build_grid_lines(board_gray.shape[0], best_size)
        best_clues: dict[tuple[int, int], int] = {}
        best_entries: list[dict[str, Any]] = []
        best_component_mask = np.zeros_like(board_gray, dtype=bool)
        best_key: tuple[int, int, int, float, int] | None = None

        for candidate_size in AUTO_BOARD_SIZES:
            x_lines = self._build_grid_lines(board_gray.shape[1], candidate_size)
            y_lines = self._build_grid_lines(board_gray.shape[0], candidate_size)

            clues, clue_entries, clue_component_mask, alignment_score = self._detect_clues(
                board_gray,
                x_lines,
                y_lines,
                board_size=candidate_size,
            )

            clue_values = sorted(clues.values())
            has_start = 1 in clue_values
            contiguous = bool(clue_values) and clue_values == list(range(1, len(clue_values) + 1))

            key = (
                0 if has_start else 1,
                0 if contiguous else 1,
                -len(clue_values),
                float(alignment_score),
                abs(candidate_size - DEFAULT_BOARD_SIZE),
            )

            if best_key is None or key < best_key:
                best_key = key
                best_size = candidate_size
                best_x_lines = x_lines
                best_y_lines = y_lines
                best_clues = clues
                best_entries = clue_entries
                best_component_mask = clue_component_mask

        return int(best_size), best_x_lines, best_y_lines, best_clues, best_entries, best_component_mask

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
        board_size: int,
        clue_component_mask: np.ndarray | None = None,
    ) -> tuple[list[list[bool]], list[list[bool]]]:
        wall_mask = board_gray < WALL_PIXEL_THRESHOLD
        if clue_component_mask is not None and clue_component_mask.shape == wall_mask.shape:
            wall_mask = np.logical_and(wall_mask, np.logical_not(clue_component_mask))

        x_steps = np.diff(np.array(x_lines))
        y_steps = np.diff(np.array(y_lines))
        average_cell = float(min(np.mean(x_steps), np.mean(y_steps)))

        pad = max(2, int(round(average_cell * 0.08)))
        probe = max(2, int(round(average_cell * 0.05)))
        ratio_threshold = 0.35

        blocked_h = [[False for _ in range(board_size)] for _ in range(board_size - 1)]
        blocked_v = [[False for _ in range(board_size - 1)] for _ in range(board_size)]

        height, width = board_gray.shape

        for row in range(board_size - 1):
            boundary_y = y_lines[row + 1]
            for col in range(board_size):
                x1 = max(0, x_lines[col] + pad)
                x2 = min(width, x_lines[col + 1] - pad)
                y1 = max(0, boundary_y - probe)
                y2 = min(height, boundary_y + probe + 1)

                patch = wall_mask[y1:y2, x1:x2]
                ratio = float(np.mean(patch)) if patch.size else 0.0
                blocked_h[row][col] = ratio > ratio_threshold

        for row in range(board_size):
            for col in range(board_size - 1):
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
        board_size: int,
    ) -> tuple[dict[tuple[int, int], int], list[dict[str, Any]], np.ndarray, float]:
        clue_mask = (board_gray < CLUE_COMPONENT_THRESHOLD).astype(np.uint8) * 255
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(clue_mask, connectivity=8)

        clues: dict[tuple[int, int], int] = {}
        entries_by_cell: dict[tuple[int, int], dict[str, Any]] = {}
        clue_component_mask = np.zeros_like(clue_mask, dtype=bool)
        offset_by_cell: dict[tuple[int, int], float] = {}

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

            row = self._map_to_cell(center_y, y_lines, board_size)
            col = self._map_to_cell(center_x, x_lines, board_size)
            if row is None or col is None:
                continue

            cell_width = max(1.0, float(x_lines[col + 1] - x_lines[col]))
            cell_height = max(1.0, float(y_lines[row + 1] - y_lines[row]))
            cell_center_x = (x_lines[col] + x_lines[col + 1]) / 2.0
            cell_center_y = (y_lines[row] + y_lines[row + 1]) / 2.0
            normalized_offset = (
                abs(center_x - cell_center_x) / (cell_width / 2.0)
                + abs(center_y - cell_center_y) / (cell_height / 2.0)
            ) / 2.0

            roi = board_gray[y : y + height, x : x + width]
            prediction = self._ocr.predict(roi, max_value=board_size * board_size)
            if prediction is None:
                continue

            clue_component_mask[labels == label] = True

            cell = (row, col)
            current = entries_by_cell.get(cell)
            if current is not None and float(current["confidence"]) >= prediction.score:
                continue

            clues[cell] = int(prediction.value)
            offset_by_cell[cell] = float(normalized_offset)
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
        alignment_score = (
            float(sum(offset_by_cell.values()) / len(offset_by_cell))
            if offset_by_cell
            else float("inf")
        )
        return clues, clue_entries, clue_component_mask, alignment_score

    def _map_to_cell(self, coordinate: float, lines: list[int], board_size: int) -> int | None:
        index = int(np.searchsorted(lines, coordinate, side="right") - 1)
        if index < 0 or index >= board_size:
            return None
        return index
