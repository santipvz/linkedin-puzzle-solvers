from __future__ import annotations

import glob
import itertools
import os
import random
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.neighbors import KNeighborsClassifier


BOARD_SIZE = 6
GRID_LINE_COUNT = BOARD_SIZE + 1
OCR_INPUT_SIZE = 28
OCR_MIN_CONFIDENCE = 0.52
OCR_STRONG_CONFIDENCE = 0.78


@dataclass(slots=True)
class _LineGroup:
    start: int
    end: int
    strength: float

    @property
    def center(self) -> int:
        return int((self.start + self.end) // 2)


class _MiniSudokuOcr:
    def __init__(self) -> None:
        self._model = self._train_model()

    def predict(self, normalized_digit: np.ndarray) -> tuple[int, float, list[tuple[int, float]]]:
        feature = normalized_digit.reshape(1, -1).astype(np.float32)
        probabilities = self._model.predict_proba(feature)[0]
        classes = self._model.classes_

        ranked_indices = np.argsort(probabilities)[::-1]
        ranked = [(int(classes[index]), float(probabilities[index])) for index in ranked_indices]

        best_digit, best_confidence = ranked[0]
        return best_digit, best_confidence, ranked

    def _train_model(self) -> KNeighborsClassifier:
        features, labels = self._load_or_build_training_dataset()

        model = KNeighborsClassifier(n_neighbors=3, weights="distance")
        model.fit(np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int32))
        return model

    def _load_or_build_training_dataset(self) -> tuple[list[np.ndarray], list[int]]:
        cache_path = self._dataset_cache_path()
        if cache_path.exists():
            try:
                cached = np.load(cache_path)
                cached_features = cached["features"].astype(np.float32)
                cached_labels = cached["labels"].astype(np.int32)
                if cached_features.ndim == 2 and len(cached_features) == len(cached_labels) and len(cached_labels) > 0:
                    return [row for row in cached_features], [int(value) for value in cached_labels.tolist()]
            except Exception:
                cache_path.unlink(missing_ok=True)

        rng = random.Random(1337)
        np_rng = np.random.default_rng(1337)
        features: list[np.ndarray] = []
        labels: list[int] = []

        font_paths = self._candidate_font_paths()

        for digit in range(1, BOARD_SIZE + 1):
            for font_path in font_paths:
                for font_size in (24, 28, 32, 36):
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                    except OSError:
                        continue

                    for _ in range(7):
                        rendered = self._render_digit_canvas(digit, font, rng, np_rng)
                        normalized = _normalize_digit_mask(rendered)
                        if normalized is None:
                            continue

                        features.append(normalized.reshape(-1).astype(np.float32))
                        labels.append(digit)

        if not features:
            fallback_features, fallback_labels = self._build_fallback_dataset()
            features.extend(fallback_features)
            labels.extend(fallback_labels)

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                cache_path,
                features=np.asarray(features, dtype=np.float32),
                labels=np.asarray(labels, dtype=np.int32),
            )
        except Exception:
            pass

        return features, labels

    def _dataset_cache_path(self) -> Path:
        return Path(tempfile.gettempdir()) / "linkedin_puzzle_solvers_sudoku_ocr_v2.npz"

    def _candidate_font_paths(self) -> list[str]:
        patterns = [
            "/usr/share/fonts/truetype/msttcorefonts/*.ttf",
            "/usr/share/fonts/truetype/open-sans/*.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-*.ttf",
            "/usr/share/fonts/opentype/cantarell/*.otf",
            "/usr/share/fonts/truetype/paratype/PT*.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans*.ttf",
        ]
        style_keywords = (
            "regular",
            "book",
            "roman",
            "medium",
            "caption",
            "verdana",
            "opensans",
            "noto",
            "cantarell",
            "dejavusans",
        )

        collected: list[str] = []
        for pattern in patterns:
            for path in sorted(glob.glob(pattern)):
                filename = os.path.basename(path).lower()
                if any(keyword in filename for keyword in style_keywords):
                    collected.append(path)

        unique_paths: list[str] = []
        seen: set[str] = set()
        for path in collected:
            if path in seen:
                continue
            seen.add(path)
            unique_paths.append(path)

        if unique_paths:
            return unique_paths[:16]

        return []

    def _render_digit_canvas(
        self,
        digit: int,
        font: Any,
        rng: random.Random,
        np_rng: np.random.Generator,
    ) -> np.ndarray:
        canvas = Image.new("L", (64, 64), 255)
        draw = ImageDraw.Draw(canvas)

        text = str(digit)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (64 - text_width) // 2 + rng.randint(-5, 5)
        y = (64 - text_height) // 2 + rng.randint(-5, 5)
        fill = rng.randint(72, 150)

        draw.text((x, y), text, fill=fill, font=font)

        image = np.array(canvas, dtype=np.uint8)

        if rng.random() < 0.6:
            image = cv2.GaussianBlur(image, (3, 3), 0)

        if rng.random() < 0.35:
            noise = np_rng.normal(0, 6, image.shape).astype(np.int16)
            image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        if rng.random() < 0.45:
            alpha = rng.uniform(0.9, 1.18)
            beta = rng.uniform(-22, 20)
            image = np.clip(image.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

        angle = rng.uniform(-8, 8)
        scale = rng.uniform(0.82, 1.2)
        matrix = cv2.getRotationMatrix2D((32, 32), angle, scale)
        matrix[:, 2] += [rng.uniform(-3, 3), rng.uniform(-3, 3)]
        image = cv2.warpAffine(image, matrix, (64, 64), borderValue=(255.0, 255.0, 255.0))

        return image

    def _build_fallback_dataset(self) -> tuple[list[np.ndarray], list[int]]:
        features: list[np.ndarray] = []
        labels: list[int] = []

        fallback_font = ImageFont.load_default()
        rng = random.Random(2026)
        np_rng = np.random.default_rng(2026)

        for digit in range(1, BOARD_SIZE + 1):
            for _ in range(80):
                rendered = self._render_digit_canvas(digit, fallback_font, rng, np_rng)
                normalized = _normalize_digit_mask(rendered)
                if normalized is None:
                    continue
                features.append(normalized.reshape(-1).astype(np.float32))
                labels.append(digit)

        return features, labels


@lru_cache(maxsize=1)
def _get_ocr_model() -> _MiniSudokuOcr:
    return _MiniSudokuOcr()


class MiniSudokuImageParser:
    def __init__(self) -> None:
        self._ocr = _get_ocr_model()

    def parse_image(self, image_path: str | Path) -> dict[str, Any]:
        path = Path(image_path)
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not load image: {path}")

        board_crop, bbox = self._extract_board_crop(image)
        row_lines, col_lines = self._detect_grid_lines(board_crop)
        board, fixed_cells, confidence_stats = self._parse_cells(board_crop, row_lines, col_lines)

        return {
            "board": board,
            "fixed_cells": fixed_cells,
            "ocr": confidence_stats,
            "board_bbox": bbox,
            "grid_lines": {
                "rows": row_lines,
                "cols": col_lines,
            },
        }

    def _extract_board_crop(self, image: np.ndarray) -> tuple[np.ndarray, dict[str, int]]:
        image_height, image_width = image.shape[:2]
        bbox = self._detect_board_bbox(image)
        if bbox is None:
            bbox = self._detect_board_bbox_from_line_projections(image)

        if bbox is None:
            return image, {
                "x": 0,
                "y": 0,
                "width": int(image_width),
                "height": int(image_height),
            }

        x, y, width, height = bbox
        trim = max(1, int(min(width, height) * 0.003))

        x1 = max(0, x + trim)
        y1 = max(0, y + trim)
        x2 = min(image_width, x + width - trim)
        y2 = min(image_height, y + height - trim)

        if x2 - x1 < 120 or y2 - y1 < 120:
            raise ValueError("Detected board area is too small.")

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
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        masks: list[np.ndarray] = []

        adaptive = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            25,
            4,
        )
        adaptive = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
        masks.append(adaptive)

        edges = cv2.Canny(blurred, 35, 120)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        masks.append(edges)

        image_height, image_width = gray.shape
        image_area = image_height * image_width
        center_x = image_width / 2
        center_y = image_height / 2

        best_score = float("-inf")
        best_bbox: tuple[int, int, int, int] | None = None

        for mask in masks:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)
                if width <= 0 or height <= 0:
                    continue

                bbox_area = width * height
                if bbox_area < image_area * 0.05:
                    continue

                aspect_ratio = width / height
                if not (0.72 <= aspect_ratio <= 1.32):
                    continue

                contour_area = cv2.contourArea(contour)
                fill_ratio = contour_area / max(1, bbox_area)
                if fill_ratio < 0.08:
                    continue

                contour_center_x = x + width / 2
                contour_center_y = y + height / 2
                center_distance = float(np.hypot(contour_center_x - center_x, contour_center_y - center_y))

                touches_edge = (
                    x <= 1
                    or y <= 1
                    or x + width >= image_width - 1
                    or y + height >= image_height - 1
                )
                edge_touch_penalty = 0.97 if touches_edge else 1.0

                score = (bbox_area * fill_ratio * edge_touch_penalty) - (center_distance * 190)
                if score > best_score:
                    best_score = score
                    best_bbox = (x, y, width, height)

        return best_bbox

    def _detect_board_bbox_from_line_projections(self, image: np.ndarray) -> tuple[int, int, int, int] | None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        image_area = height * width

        best: tuple[float, list[int], list[int]] | None = None

        for block_size in (15, 17, 19, 21):
            if block_size >= min(height, width):
                continue

            for constant in (2, 3, 4, 5):
                binary = cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    block_size,
                    constant,
                )

                for frac in (0.09, 0.11, 0.13, 0.15, 0.17):
                    horizontal_kernel = max(12, int(width * frac))
                    vertical_kernel = max(12, int(height * frac))

                    horizontal_lines = cv2.morphologyEx(
                        binary,
                        cv2.MORPH_OPEN,
                        cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_kernel, 1)),
                    )
                    vertical_lines = cv2.morphologyEx(
                        binary,
                        cv2.MORPH_OPEN,
                        cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel)),
                    )

                    row_projection = horizontal_lines.sum(axis=1)
                    col_projection = vertical_lines.sum(axis=0)

                    row_groups = self._extract_line_groups(row_projection, 255 * max(8, width // 8))
                    col_groups = self._extract_line_groups(col_projection, 255 * max(8, height // 8))

                    col_lines, col_score = self._select_regular_line_subset(col_groups, GRID_LINE_COUNT)
                    if col_lines is None:
                        continue

                    col_step = (col_lines[-1] - col_lines[0]) / BOARD_SIZE
                    if col_step < 20:
                        continue

                    row_lines, row_score = self._select_regular_line_subset(row_groups, GRID_LINE_COUNT)

                    if row_lines is not None:
                        row_step = (row_lines[-1] - row_lines[0]) / BOARD_SIZE
                    else:
                        row_step = 0.0

                    if row_lines is None or abs(row_step - col_step) > max(row_step, col_step) * 0.18:
                        inferred_rows, inferred_score = self._infer_lines_with_fixed_step(
                            row_projection,
                            col_step,
                            GRID_LINE_COUNT,
                        )
                        if inferred_rows is None or inferred_score is None:
                            continue
                        row_lines = inferred_rows
                        row_score = inferred_score
                        row_step = (row_lines[-1] - row_lines[0]) / BOARD_SIZE

                    if row_step < 20:
                        continue

                    board_width = col_lines[-1] - col_lines[0]
                    board_height = row_lines[-1] - row_lines[0]
                    board_area = board_width * board_height
                    if board_area < image_area * 0.03:
                        continue

                    square_penalty = abs(col_step - row_step)
                    score = (
                        (col_score or 0.0)
                        + (row_score or 0.0)
                        + (board_area * 0.003)
                        - (square_penalty * 120)
                    )

                    if best is None or score > best[0]:
                        best = (score, row_lines, col_lines)

        if best is None:
            return None

        row_lines = best[1]
        col_lines = best[2]

        x = int(col_lines[0])
        y = int(row_lines[0])
        width_box = int(col_lines[-1] - col_lines[0])
        height_box = int(row_lines[-1] - row_lines[0])

        if width_box < 120 or height_box < 120:
            return None

        return x, y, width_box, height_box

    def _detect_grid_lines(self, board_crop: np.ndarray) -> tuple[list[int], list[int]]:
        gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape

        best: tuple[float, list[int], list[int]] | None = None

        for block_size in (15, 17, 19, 21):
            if block_size >= min(height, width):
                continue

            for constant in (2, 3, 4, 5):
                binary = cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    block_size,
                    constant,
                )

                for frac in (0.09, 0.11, 0.13, 0.15, 0.17):
                    horizontal_kernel = max(12, int(width * frac))
                    vertical_kernel = max(12, int(height * frac))

                    horizontal_lines = cv2.morphologyEx(
                        binary,
                        cv2.MORPH_OPEN,
                        cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_kernel, 1)),
                    )
                    vertical_lines = cv2.morphologyEx(
                        binary,
                        cv2.MORPH_OPEN,
                        cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel)),
                    )

                    row_projection = horizontal_lines.sum(axis=1)
                    col_projection = vertical_lines.sum(axis=0)

                    row_groups = self._extract_line_groups(row_projection, 255 * max(10, width // 5))
                    col_groups = self._extract_line_groups(col_projection, 255 * max(10, height // 5))

                    row_lines, row_score = self._select_regular_line_subset(row_groups, GRID_LINE_COUNT)
                    col_lines, col_score = self._select_regular_line_subset(col_groups, GRID_LINE_COUNT)
                    if row_lines is None or col_lines is None:
                        continue

                    score = self._score_line_candidate(row_lines, col_lines, height, width)
                    score += (row_score or 0.0) * 0.0005
                    score += (col_score or 0.0) * 0.0005

                    if best is None or score > best[0]:
                        best = (score, row_lines, col_lines)

        if best is None:
            raise ValueError("Could not detect Sudoku grid lines.")

        row_lines, col_lines = best[1], best[2]
        if len(row_lines) != GRID_LINE_COUNT or len(col_lines) != GRID_LINE_COUNT:
            raise ValueError(
                f"Expected {GRID_LINE_COUNT} grid lines per axis, got {len(row_lines)}x{len(col_lines)}."
            )

        return row_lines, col_lines

    def _extract_line_groups(self, projection: np.ndarray, min_signal: float) -> list[_LineGroup]:
        indices = np.where(projection > min_signal)[0]
        if indices.size == 0:
            return []

        split_indices = np.where(np.diff(indices) > 1)[0] + 1
        chunks = np.split(indices, split_indices)

        groups: list[_LineGroup] = []
        for chunk in chunks:
            if chunk.size == 0:
                continue
            start = int(chunk[0])
            end = int(chunk[-1])
            strength = float(np.sum(projection[start : end + 1]))
            groups.append(_LineGroup(start=start, end=end, strength=strength))

        return groups

    def _select_regular_line_subset(
        self,
        groups: list[_LineGroup],
        expected_count: int,
    ) -> tuple[list[int] | None, float | None]:
        if len(groups) < expected_count:
            return None, None

        strongest = sorted(groups, key=lambda group: group.strength, reverse=True)[:14]
        strongest = sorted(strongest, key=lambda group: group.center)
        if len(strongest) < expected_count:
            return None, None

        best_lines: list[int] | None = None
        best_score: float | None = None

        for combo in itertools.combinations(range(len(strongest)), expected_count):
            lines = [strongest[index].center for index in combo]
            steps = np.diff(lines)
            if steps.size != expected_count - 1:
                continue
            if int(np.min(steps)) < 18:
                continue

            steps_std = float(np.std(steps))
            step_range = float(np.max(steps) - np.min(steps))
            strength = float(sum(strongest[index].strength for index in combo))

            score = strength * 0.001
            score -= steps_std * 35
            score -= step_range * 8

            if best_score is None or score > best_score:
                best_score = score
                best_lines = lines

        return best_lines, best_score

    def _infer_lines_with_fixed_step(
        self,
        projection: np.ndarray,
        step: float,
        line_count: int,
    ) -> tuple[list[int] | None, float | None]:
        axis_len = int(len(projection))
        span = step * (line_count - 1)
        if span < 80 or span >= axis_len - 2:
            return None, None

        window = max(2, int(round(step * 0.07)))
        max_start = int(axis_len - span - 1)
        if max_start <= 0:
            return None, None

        best_score: float | None = None
        best_lines: list[int] | None = None

        for start in range(max_start):
            aligned_lines: list[int] = []
            strengths: list[float] = []

            for index in range(line_count):
                center = int(round(start + index * step))
                x1 = max(0, center - window)
                x2 = min(axis_len, center + window + 1)
                if x2 <= x1:
                    aligned_lines.append(center)
                    strengths.append(0.0)
                    continue

                local_projection = projection[x1:x2]
                local_offset = int(np.argmax(local_projection))
                aligned = x1 + local_offset
                aligned_lines.append(aligned)
                strengths.append(float(local_projection[local_offset]))

            score = (
                strengths[1] * 1.4
                + strengths[2] * 1.4
                + strengths[3] * 1.4
                + strengths[4] * 1.4
                + strengths[5] * 1.4
                + strengths[0] * 0.8
                + strengths[6] * 0.8
            )

            if best_score is None or score > best_score:
                best_score = score
                best_lines = aligned_lines

        return best_lines, best_score

    def _score_line_candidate(self, rows: list[int], cols: list[int], height: int, width: int) -> float:
        score = 0.0

        score -= abs(len(rows) - GRID_LINE_COUNT) * 420
        score -= abs(len(cols) - GRID_LINE_COUNT) * 420

        if len(rows) >= 2:
            row_steps = np.diff(rows)
            expected_step = (height - 1) / BOARD_SIZE
            score -= float(np.std(row_steps)) * 7.0
            score -= abs(float(np.mean(row_steps)) - expected_step) * 0.8

        if len(cols) >= 2:
            col_steps = np.diff(cols)
            expected_step = (width - 1) / BOARD_SIZE
            score -= float(np.std(col_steps)) * 7.0
            score -= abs(float(np.mean(col_steps)) - expected_step) * 0.8

            col_cell = float(np.mean(col_steps))
            row_cell = float(np.mean(np.diff(rows))) if len(rows) >= 2 else col_cell
            score -= abs(row_cell - col_cell) * 4.0

        score += min(len(rows), GRID_LINE_COUNT) * 16
        score += min(len(cols), GRID_LINE_COUNT) * 16

        return score

    def _parse_cells(
        self,
        board_crop: np.ndarray,
        row_lines: list[int],
        col_lines: list[int],
    ) -> tuple[list[list[int]], list[dict[str, Any]], dict[str, float | int]]:
        gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(board_crop, cv2.COLOR_BGR2HSV)
        orange_mask = cv2.inRange(
            hsv,
            np.array([6, 90, 90], dtype=np.uint8),
            np.array([40, 255, 255], dtype=np.uint8),
        )

        board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        fixed_cells: list[dict[str, Any]] = []
        confidences: list[float] = []
        uncertain_count = 0
        overlay_cell_count = 0

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                y1 = int(max(0, row_lines[row] + 1))
                y2 = int(min(gray.shape[0], row_lines[row + 1] - 1))
                x1 = int(max(0, col_lines[col] + 1))
                x2 = int(min(gray.shape[1], col_lines[col + 1] - 1))

                if y2 <= y1 + 6 or x2 <= x1 + 6:
                    continue

                overlay_ratio = float(np.count_nonzero(orange_mask[y1:y2, x1:x2])) / max(
                    1,
                    (y2 - y1) * (x2 - x1),
                )
                if overlay_ratio > 0.02:
                    overlay_cell_count += 1

                cell = gray[y1:y2, x1:x2]
                normalized_digit = _normalize_digit_mask(cell)
                if normalized_digit is None:
                    continue

                value, confidence, ranked = self._ocr.predict(normalized_digit)
                if confidence < OCR_MIN_CONFIDENCE:
                    continue

                board[row][col] = int(value)
                confidences.append(float(confidence))
                if confidence < OCR_STRONG_CONFIDENCE:
                    uncertain_count += 1

                fixed_cells.append(
                    {
                        "row": int(row),
                        "col": int(col),
                        "value": int(value),
                        "confidence": float(confidence),
                        "overlay_ratio": overlay_ratio,
                        "candidates": [
                            {"value": int(candidate_value), "confidence": float(candidate_confidence)}
                            for candidate_value, candidate_confidence in ranked[:3]
                        ],
                    }
                )

        avg_confidence = float(np.mean(confidences)) if confidences else 0.0
        min_confidence = float(np.min(confidences)) if confidences else 0.0

        ocr_stats: dict[str, float | int] = {
            "fixed_count": int(len(fixed_cells)),
            "avg_confidence": avg_confidence,
            "min_confidence": min_confidence,
            "uncertain_count": int(uncertain_count),
            "overlay_cell_count": int(overlay_cell_count),
        }

        return board, fixed_cells, ocr_stats


def _normalize_digit_mask(cell_gray: np.ndarray) -> np.ndarray | None:
    height, width = cell_gray.shape[:2]
    if height < 12 or width < 12:
        return None

    margin_y = int(height * 0.16)
    margin_x = int(width * 0.16)

    roi = cell_gray[margin_y : height - margin_y, margin_x : width - margin_x]
    if roi.size == 0:
        return None

    block_size = 17
    if block_size >= min(roi.shape[0], roi.shape[1]):
        block_size = max(3, min(roi.shape[0], roi.shape[1]) // 2 * 2 + 1)
    if block_size < 3:
        return None

    binary = cv2.adaptiveThreshold(
        roi,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        3,
    )
    binary = cv2.medianBlur(binary, 3)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if component_count <= 1:
        return None

    roi_height, roi_width = binary.shape
    min_area = max(12, (roi_height * roi_width) // 250)
    max_area = max(min_area + 1, (roi_height * roi_width) // 2)

    best_component = -1
    best_score = float("-inf")

    for label in range(1, component_count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])

        if area < min_area or area > max_area:
            continue
        if width < 2 or height < 4:
            continue

        center_x = x + width / 2
        center_y = y + height / 2
        distance_penalty = float(np.hypot(center_x - (roi_width / 2), center_y - (roi_height / 2))) * 0.7
        score = float(area) - distance_penalty

        if score > best_score:
            best_score = score
            best_component = label

    if best_component < 0:
        return None

    mask = (labels == best_component).astype(np.uint8) * 255
    ys, xs = np.where(mask > 0)
    if ys.size == 0 or xs.size == 0:
        return None

    y1, y2 = int(ys.min()), int(ys.max() + 1)
    x1, x2 = int(xs.min()), int(xs.max() + 1)

    digit = mask[y1:y2, x1:x2]
    if digit.size == 0:
        return None

    square_size = max(digit.shape[0], digit.shape[1]) + 10
    square = np.zeros((square_size, square_size), dtype=np.uint8)
    offset_y = (square_size - digit.shape[0]) // 2
    offset_x = (square_size - digit.shape[1]) // 2
    square[offset_y : offset_y + digit.shape[0], offset_x : offset_x + digit.shape[1]] = digit

    normalized = cv2.resize(square, (OCR_INPUT_SIZE, OCR_INPUT_SIZE), interpolation=cv2.INTER_NEAREST)
    if int(np.count_nonzero(normalized)) < 25:
        return None

    return (normalized > 0).astype(np.float32)
