from __future__ import annotations

import glob
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.commons import BoardBBox, crop_board, external_contour_bbox_candidates, load_bgr_image, uniform_grid_bounds
from core.vision import CosineTemplateMatcher, OcrPrediction, build_parsed_board_payload


MIN_BOARD_SIZE = 5
MAX_BOARD_SIZE = 8
OCR_SIZE = 42
OCR_DARK_THRESHOLD = 120


class _LetterOcr:
    def __init__(self) -> None:
        self._letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        features, labels = self._load_or_build_templates()
        self._matcher = CosineTemplateMatcher(features, labels)

    def predict(self, cell_gray: np.ndarray) -> OcrPrediction[str] | None:
        normalized = self._normalize_letter(cell_gray)
        if normalized is None:
            return None
        return self._matcher.predict(normalized, limit=5)

    def predict_many(self, cells_gray: list[np.ndarray]) -> tuple[OcrPrediction[str] | None, ...]:
        results: list[OcrPrediction[str] | None] = [None] * len(cells_gray)
        normalized_features: list[np.ndarray] = []
        normalized_indices: list[int] = []
        for index, cell_gray in enumerate(cells_gray):
            normalized = self._normalize_letter(cell_gray)
            if normalized is None:
                continue
            normalized_features.append(normalized.reshape(-1))
            normalized_indices.append(index)
        if normalized_features:
            predictions = self._matcher.predict_many(np.asarray(normalized_features, dtype=np.float32), limit=5)
            for index, prediction in zip(normalized_indices, predictions):
                results[index] = prediction
        return tuple(results)

    def _load_or_build_templates(self) -> tuple[np.ndarray, list[str]]:
        cache_path = Path(tempfile.gettempdir()) / "linkedin_puzzle_solvers_wend_letters_v1.npz"
        if cache_path.exists():
            try:
                cached = np.load(cache_path)
                return cached["features"].astype(np.float32), [str(value) for value in cached["labels"].tolist()]
            except (OSError, ValueError, KeyError, EOFError):
                cache_path.unlink(missing_ok=True)

        features: list[np.ndarray] = []
        labels: list[str] = []
        for font_path in self._candidate_font_paths():
            for size in (24, 28, 32, 36, 40):
                try:
                    font = ImageFont.truetype(font_path, size)
                except OSError:
                    continue

                for letter in self._letters:
                    for offset_x, offset_y in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                        rendered = self._render_letter(letter, font, offset_x, offset_y)
                        normalized = self._normalize_mask(rendered)
                        if normalized is None:
                            continue
                        features.append(normalized.reshape(-1).astype(np.float32))
                        labels.append(letter)

        if not features:
            raise RuntimeError("Could not build Wend letter OCR templates.")

        feature_array = np.asarray(features, dtype=np.float32)
        try:
            np.savez_compressed(cache_path, features=feature_array, labels=np.asarray(labels))
        except OSError:
            pass
        return feature_array, labels

    def _render_letter(self, letter: str, font: ImageFont.FreeTypeFont, offset_x: int, offset_y: int) -> np.ndarray:
        image = Image.new("L", (OCR_SIZE, OCR_SIZE), 0)
        draw = ImageDraw.Draw(image)
        left, top, right, bottom = draw.textbbox((0, 0), letter, font=font)
        x = ((OCR_SIZE - (right - left)) // 2) - left + offset_x
        y = ((OCR_SIZE - (bottom - top)) // 2) - top + offset_y
        draw.text((x, y), letter, font=font, fill=255)
        return np.asarray(image, dtype=np.uint8)

    def _normalize_letter(self, cell_gray: np.ndarray) -> np.ndarray | None:
        if cell_gray.size == 0:
            return None

        blurred = cv2.GaussianBlur(cell_gray, (3, 3), 0)
        mask = (blurred < OCR_DARK_THRESHOLD).astype(np.uint8) * 255
        height, width = mask.shape
        margin_y = max(2, int(height * 0.12))
        margin_x = max(2, int(width * 0.12))
        mask[:margin_y, :] = 0
        mask[-margin_y:, :] = 0
        mask[:, :margin_x] = 0
        mask[:, -margin_x:] = 0
        return self._normalize_mask(mask)

    @staticmethod
    def _normalize_mask(mask: np.ndarray) -> np.ndarray | None:
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if component_count <= 1:
            return None

        keep = np.zeros_like(mask)
        min_area = max(6, mask.size // 260)
        for label in range(1, component_count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area >= min_area:
                keep[labels == label] = 255

        if np.count_nonzero(keep) == 0:
            return None

        ys, xs = np.where(keep > 0)
        y1, y2 = int(ys.min()), int(ys.max() + 1)
        x1, x2 = int(xs.min()), int(xs.max() + 1)
        glyph = keep[y1:y2, x1:x2]
        side = max(glyph.shape[0], glyph.shape[1]) + 8
        square = np.zeros((side, side), dtype=np.uint8)
        y = (side - glyph.shape[0]) // 2
        x = (side - glyph.shape[1]) // 2
        square[y : y + glyph.shape[0], x : x + glyph.shape[1]] = glyph
        return cv2.resize(square, (OCR_SIZE, OCR_SIZE), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0

    @staticmethod
    def _candidate_font_paths() -> list[str]:
        patterns = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-*.ttf",
        ]
        paths: list[str] = []
        for pattern in patterns:
            paths.extend(sorted(glob.glob(pattern)))
        return list(dict.fromkeys(path for path in paths if os.path.exists(path)))


@lru_cache(maxsize=1)
def _get_ocr() -> _LetterOcr:
    return _LetterOcr()


class WendImageParser:
    def parse_image(self, image_path: str | Path) -> dict[str, Any]:
        image = load_bgr_image(image_path)

        board_crop, bbox = self._extract_board_crop(image)
        lengths = self._parse_lengths(image, bbox)
        board_size, board, cell_predictions = self._parse_best_board(board_crop, lengths)

        visible_cells = sum(1 for row in board for value in row if value is not None)
        grid = uniform_grid_bounds(width=board_crop.shape[1], height=board_crop.shape[0], board_size=board_size)
        return build_parsed_board_payload(
            board_size=board_size,
            board_bbox=bbox,
            grid=grid,
            extra_fields={
                "board": board,
                "lengths": lengths,
                "visible_cells": visible_cells,
                "ocr": {
                "cells": cell_predictions,
                "min_confidence": min((float(cell["confidence"]) for cell in cell_predictions), default=0.0),
                "avg_confidence": float(np.mean([float(cell["confidence"]) for cell in cell_predictions])) if cell_predictions else 0.0,
                },
            },
        )

    def _extract_board_crop(self, image: np.ndarray) -> tuple[np.ndarray, dict[str, int]]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        dark = cv2.inRange(gray, 0, 90)
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        height, width = gray.shape

        best: tuple[float, BoardBBox] | None = None
        for candidate in external_contour_bbox_candidates(dark):
            y, w, h = candidate.bbox.y, candidate.bbox.width, candidate.bbox.height
            if w < width * 0.25 or h < height * 0.25:
                continue
            if w < min(width, height) * 0.65 or h < min(width, height) * 0.65:
                continue
            aspect = w / max(h, 1)
            if not 0.75 <= aspect <= 1.25:
                continue
            score = float(w * h) - abs(w - h) * 1000.0 - y * 0.1
            if best is None or score > best[0]:
                best = (score, candidate.bbox)

        if best is None and 0.85 <= width / max(height, 1) <= 1.15:
            bbox = BoardBBox.full_image(image)
        elif best is None:
            side = min(width, height)
            bbox = BoardBBox(x=max(0, (width - side) // 2), y=0, width=side, height=side)
        else:
            _, bbox = best

        pad = max(0, int(min(bbox.width, bbox.height) * 0.01))
        cropped = crop_board(image, bbox, inset_pixels=pad)
        if cropped is None:
            raise ValueError("Detected Wend board is outside the image.")
        board_crop, actual_bbox = cropped
        return board_crop, actual_bbox.to_payload()

    def _parse_best_board(
        self,
        board_crop: np.ndarray,
        lengths: list[int],
    ) -> tuple[int, list[list[str | None]], list[dict[str, Any]]]:
        expected_visible = sum(lengths) if lengths else None
        parsed_candidates: list[
            tuple[tuple[float, float, float, float], int, list[list[str | None]], list[dict[str, Any]]]
        ] = []

        for board_size in range(MIN_BOARD_SIZE, MAX_BOARD_SIZE + 1):
            board, predictions = self._parse_board(board_crop, board_size)
            visible_cells = sum(value is not None for row in board for value in row)
            unknown_cells = sum(value == "?" for row in board for value in row)
            confidence = float(np.mean([item["confidence"] for item in predictions])) if predictions else 0.0
            mismatch = abs(visible_cells - expected_visible) if expected_visible is not None else 0
            grid_score = self._grid_alignment_score(board_crop, board_size)
            score = (float(mismatch), -grid_score, float(unknown_cells), -confidence)
            parsed_candidates.append((score, board_size, board, predictions))

        _, board_size, board, predictions = min(parsed_candidates, key=lambda item: item[0])
        return board_size, board, predictions

    @staticmethod
    def _grid_alignment_score(board_crop: np.ndarray, board_size: int) -> float:
        gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)
        gradient_x = np.percentile(np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)), 60, axis=0)
        gradient_y = np.percentile(np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)), 60, axis=1)
        height, width = gray.shape
        radius = max(3, int(round(min(height, width) / board_size * 0.12)))
        signals: list[float] = []
        for index in range(1, board_size):
            x = int(round(index * width / board_size))
            y = int(round(index * height / board_size))
            signals.append(float(np.max(gradient_x[max(0, x - radius) : min(width, x + radius + 1)])))
            signals.append(float(np.max(gradient_y[max(0, y - radius) : min(height, y + radius + 1)])))
        return float(np.mean(signals)) if signals else 0.0

    def _parse_board(
        self,
        board_crop: np.ndarray,
        board_size: int,
    ) -> tuple[list[list[str | None]], list[dict[str, Any]]]:
        gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)
        ocr = _get_ocr()
        grid = uniform_grid_bounds(width=gray.shape[1], height=gray.shape[0], board_size=board_size)
        cells = grid.cells()
        board: list[list[str | None]] = [[None for _ in range(board_size)] for _ in range(board_size)]
        predictions: list[dict[str, Any]] = []
        visible_cells: list[tuple[int, int, np.ndarray]] = []

        for row in range(board_size):
            for col in range(board_size):
                x, y, width, height = cells[row][col]
                cell = gray[y : y + height, x : x + width]
                center = cell[cell.shape[0] // 4 : cell.shape[0] * 3 // 4, cell.shape[1] // 4 : cell.shape[1] * 3 // 4]
                if float(np.mean(center)) < 190 and float(np.std(center)) < 28:
                    continue
                visible_cells.append((row, col, cell))

        ocr_predictions = ocr.predict_many([cell for _, _, cell in visible_cells])
        for (row, col, _cell), prediction in zip(visible_cells, ocr_predictions):
            if prediction is None:
                board[row][col] = "?"
                predictions.append(
                    {
                        "row": row,
                        "col": col,
                        "letter": "?",
                        "confidence": 0.0,
                        "candidates": [],
                    }
                )
                continue

            board[row][col] = prediction.value
            predictions.append(
                {
                    "row": row,
                    "col": col,
                    "letter": prediction.value,
                    "confidence": prediction.confidence,
                    "candidates": [
                        {"letter": candidate.value, "confidence": candidate.confidence}
                        for candidate in prediction.candidates
                    ],
                }
            )

        return board, predictions

    def _parse_lengths(self, image: np.ndarray, board_bbox: dict[str, int]) -> list[int]:
        y_start = int(board_bbox["y"] + board_bbox["height"])
        if y_start >= image.shape[0] - 10:
            return []

        below = image[y_start:, :]
        gray = cv2.cvtColor(below, cv2.COLOR_BGR2GRAY)
        mask = cv2.inRange(gray, 205, 235)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        boxes: list[tuple[int, int, int, int]] = []
        min_area = max(45, int(board_bbox["width"] * board_bbox["height"] / 15000))
        max_box = max(12, int(board_bbox["width"] / MAX_BOARD_SIZE * 0.75))

        for label in range(1, component_count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_area or w > max_box * 2 or h > max_box * 2:
                continue
            if not 0.55 <= w / max(h, 1) <= 1.8:
                continue
            boxes.append((x, y, w, h))

        if not boxes:
            return []

        rows: list[list[tuple[int, int, int, int]]] = []
        for box in sorted(boxes, key=lambda item: item[1]):
            center_y = box[1] + box[3] / 2
            for row in rows:
                row_center = np.mean([existing[1] + existing[3] / 2 for existing in row])
                if abs(center_y - row_center) <= max(8, box[3] * 0.7):
                    row.append(box)
                    break
            else:
                rows.append([box])

        return [len(row) for row in rows if len(row) > 1]
