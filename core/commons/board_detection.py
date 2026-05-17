from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import cv2
import numpy as np

from core.vision.line_projection import extract_line_groups, select_regular_line_subset


SizeValidator = Callable[[int], bool]


@dataclass(frozen=True, slots=True)
class BoardGeometry:
    board_size: int
    board_bbox: dict[str, int]
    row_lines: list[int]
    col_lines: list[int]
    board_detection: dict[str, float | int | str]
    grid_detection: dict[str, float | int | bool | str]


def infer_candidate_board_sizes(
    *,
    axis_length: int,
    size_candidates: Iterable[int] | None = None,
    min_board_size: int = 2,
    max_board_size: int | None = None,
    min_cell_size: int = 14,
    max_cell_size: int = 140,
    preferred_board_size: int | None = None,
    max_candidate_count: int = 14,
    size_validator: SizeValidator | None = None,
) -> list[int]:
    min_size = max(2, int(min_board_size))
    max_size = int(max_board_size) if max_board_size is not None else None

    normalized: list[int] = []
    if size_candidates is not None:
        seen: set[int] = set()
        for raw_size in size_candidates:
            try:
                size = int(raw_size)
            except (TypeError, ValueError):
                continue

            if size < min_size:
                continue
            if max_size is not None and size > max_size:
                continue
            if size_validator is not None and not size_validator(size):
                continue
            if size in seen:
                continue

            seen.add(size)
            normalized.append(size)

        normalized.sort()

    if not normalized:
        clamped_axis = max(1, int(axis_length))
        min_cell = max(4, int(min_cell_size))
        max_cell = max(min_cell, int(max_cell_size))

        derived_min = int(np.ceil(clamped_axis / max_cell))
        derived_max = int(clamped_axis // min_cell)

        derived_min = max(min_size, derived_min)
        if max_size is not None:
            derived_max = min(derived_max, max_size)

        if derived_max < derived_min:
            derived_max = derived_min

        normalized = list(range(derived_min, derived_max + 1))
        if size_validator is not None:
            normalized = [size for size in normalized if size_validator(size)]

    if not normalized:
        fallback = preferred_board_size if preferred_board_size is not None else min_size
        fallback = max(min_size, int(fallback))
        if max_size is not None:
            fallback = min(max_size, fallback)
        if size_validator is None or size_validator(fallback):
            return [int(fallback)]
        return []

    if max_candidate_count > 0 and len(normalized) > max_candidate_count:
        normalized = _compress_candidates(
            normalized,
            max_count=max_candidate_count,
            preferred=preferred_board_size,
        )

    return normalized


def detect_board_geometry(
    image: np.ndarray,
    *,
    size_candidates: Iterable[int] | None = None,
    min_board_size: int = 2,
    max_board_size: int | None = None,
    preferred_board_size: int | None = None,
    min_cell_size: int = 14,
    max_cell_size: int = 140,
    max_candidate_count: int = 14,
    min_coverage_ratio: float = 0.35,
    size_validator: SizeValidator | None = None,
    allow_uniform_fallback: bool = True,
) -> BoardGeometry | None:
    gray = _to_grayscale(image)
    height, width = gray.shape
    axis = min(height, width)

    candidate_sizes = infer_candidate_board_sizes(
        axis_length=axis,
        size_candidates=size_candidates,
        min_board_size=min_board_size,
        max_board_size=max_board_size,
        min_cell_size=min_cell_size,
        max_cell_size=max_cell_size,
        preferred_board_size=preferred_board_size,
        max_candidate_count=max_candidate_count,
        size_validator=size_validator,
    )
    if not candidate_sizes:
        return None

    best: _CandidateDetection | None = None

    for variant_name, variant_gray in _gray_variants(gray).items():
        for block_size in _adaptive_block_sizes(axis):
            if block_size >= min(height, width):
                continue

            for constant in (2, 4, 6):
                binary = cv2.adaptiveThreshold(
                    variant_gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    block_size,
                    constant,
                )
                binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

                for frac in (0.08, 0.11, 0.14):
                    horizontal_kernel = max(8, int(width * frac))
                    vertical_kernel = max(8, int(height * frac))

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
                    if not np.any(row_projection) or not np.any(col_projection):
                        continue

                    for board_size in candidate_sizes:
                        expected_line_count = board_size + 1

                        row_groups = extract_line_groups(
                            row_projection,
                            _projection_min_signal(row_projection, width, board_size),
                        )
                        col_groups = extract_line_groups(
                            col_projection,
                            _projection_min_signal(col_projection, height, board_size),
                        )
                        if len(row_groups) < expected_line_count or len(col_groups) < expected_line_count:
                            continue

                        min_step = max(6, int(round(axis / max(2.0, board_size * 2.8))))

                        row_lines, row_strength = select_regular_line_subset(
                            row_groups,
                            expected_line_count,
                            strongest_limit=min(len(row_groups), max(12, expected_line_count + 6)),
                            min_step=min_step,
                            step_std_penalty=30.0,
                            step_range_penalty=7.0,
                        )
                        col_lines, col_strength = select_regular_line_subset(
                            col_groups,
                            expected_line_count,
                            strongest_limit=min(len(col_groups), max(12, expected_line_count + 6)),
                            min_step=min_step,
                            step_std_penalty=30.0,
                            step_range_penalty=7.0,
                        )
                        if row_lines is None or col_lines is None:
                            continue

                        normalized_rows = _normalize_lines(row_lines, axis_length=height)
                        normalized_cols = _normalize_lines(col_lines, axis_length=width)
                        if normalized_rows is None or normalized_cols is None:
                            continue

                        metrics = _grid_quality_metrics(
                            row_lines=normalized_rows,
                            col_lines=normalized_cols,
                            height=height,
                            width=width,
                            board_size=board_size,
                            min_cell_size=min_cell_size,
                            min_coverage_ratio=min_coverage_ratio,
                        )
                        if not np.isfinite(metrics["quality_score"]):
                            continue

                        score = float(metrics["quality_score"])
                        score += float((row_strength or 0.0) + (col_strength or 0.0)) * 0.0008

                        if preferred_board_size is not None:
                            score -= abs(int(board_size) - int(preferred_board_size)) * 7.0

                        candidate = _CandidateDetection(
                            board_size=int(board_size),
                            row_lines=normalized_rows,
                            col_lines=normalized_cols,
                            score=float(score),
                            source=f"projection:{variant_name}",
                            block_size=int(block_size),
                            constant=int(constant),
                            kernel_fraction=float(frac),
                            metrics=metrics,
                        )

                        if best is None or candidate.score > best.score:
                            best = candidate

    if best is None:
        if not allow_uniform_fallback:
            return None

        fallback_size = _fallback_size(candidate_sizes, preferred_board_size)
        if fallback_size <= 1:
            return None

        row_lines = _uniform_pixel_lines(height, fallback_size)
        col_lines = _uniform_pixel_lines(width, fallback_size)
        bbox = _bbox_from_lines(row_lines=row_lines, col_lines=col_lines)
        if bbox is None:
            return None

        return BoardGeometry(
            board_size=int(fallback_size),
            board_bbox=bbox,
            row_lines=row_lines,
            col_lines=col_lines,
            board_detection={
                "source": "uniform-fallback",
                "score": float("-inf"),
                "candidate_count": int(len(candidate_sizes)),
            },
            grid_detection={
                "quality_score": float("-inf"),
                "coverage_ratio": 1.0,
                "row_step_cv": 0.0,
                "col_step_cv": 0.0,
                "square_delta": 0.0,
                "center_offset": 0.0,
                "used_uniform_lines": True,
            },
        )

    bbox = _bbox_from_lines(row_lines=best.row_lines, col_lines=best.col_lines)
    if bbox is None:
        return None

    area_ratio = (bbox["width"] * bbox["height"]) / max(1.0, float(height * width))
    board_detection = {
        "source": best.source,
        "score": float(best.score),
        "candidate_count": int(len(candidate_sizes)),
        "area_ratio": float(area_ratio),
        "block_size": int(best.block_size),
        "constant": int(best.constant),
        "kernel_fraction": float(best.kernel_fraction),
    }

    grid_detection = {
        **best.metrics,
        "used_uniform_lines": False,
    }

    return BoardGeometry(
        board_size=int(best.board_size),
        board_bbox=bbox,
        row_lines=best.row_lines,
        col_lines=best.col_lines,
        board_detection=board_detection,
        grid_detection=grid_detection,
    )


def crop_to_bbox(image: np.ndarray, bbox: dict[str, int]) -> np.ndarray:
    x = int(bbox.get("x", 0))
    y = int(bbox.get("y", 0))
    width = int(bbox.get("width", 0))
    height = int(bbox.get("height", 0))

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(image.shape[1], x1 + max(1, width))
    y2 = min(image.shape[0], y1 + max(1, height))

    return image[y1:y2, x1:x2]


def to_slice_bounds(
    lines: list[int],
    *,
    offset: int,
    extent: int,
    anchor_edges: bool = True,
) -> list[int]:
    if extent <= 0:
        return []
    if len(lines) < 2:
        return [0, int(extent)]

    local = [int(round(value - offset)) for value in lines]
    local = [max(0, min(int(extent), value)) for value in local]
    if anchor_edges:
        local[0] = 0
        local[-1] = int(extent)

    last_index = len(local) - (1 if anchor_edges else 0)
    for index in range(1, last_index):
        min_allowed = local[index - 1] + 1
        max_allowed = int(extent) - (len(local) - 1 - index)
        value = int(local[index])
        value = max(min_allowed, value)
        value = min(max_allowed, value)
        local[index] = value

    if anchor_edges:
        local[0] = 0
        local[-1] = int(extent)

    return local


def build_uniform_slice_bounds(extent: int, board_size: int) -> list[int]:
    axis = max(1, int(extent))
    size = max(2, int(board_size))
    lines = np.rint(np.linspace(0, axis, size + 1)).astype(int)

    normalized = [int(value) for value in lines.tolist()]
    normalized[0] = 0
    normalized[-1] = axis

    for index in range(1, len(normalized) - 1):
        min_allowed = normalized[index - 1] + 1
        max_allowed = axis - (len(normalized) - 1 - index)
        value = normalized[index]
        value = max(min_allowed, value)
        value = min(max_allowed, value)
        normalized[index] = value

    return normalized


def build_grid_coords_from_bounds(
    row_bounds: list[int],
    col_bounds: list[int],
) -> list[list[tuple[int, int, int, int]]]:
    board_size = min(len(row_bounds), len(col_bounds)) - 1
    if board_size <= 0:
        return []

    coords: list[list[tuple[int, int, int, int]]] = []
    for row in range(board_size):
        y1 = int(row_bounds[row])
        y2 = int(row_bounds[row + 1])
        row_cells: list[tuple[int, int, int, int]] = []

        for col in range(board_size):
            x1 = int(col_bounds[col])
            x2 = int(col_bounds[col + 1])

            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            row_cells.append((x1, y1, width, height))

        coords.append(row_cells)

    return coords


@dataclass(frozen=True, slots=True)
class _CandidateDetection:
    board_size: int
    row_lines: list[int]
    col_lines: list[int]
    score: float
    source: str
    block_size: int
    constant: int
    kernel_fraction: float
    metrics: dict[str, float]


def _compress_candidates(candidates: list[int], *, max_count: int, preferred: int | None) -> list[int]:
    if len(candidates) <= max_count:
        return candidates

    selected: set[int] = set()

    if preferred is not None:
        by_distance = sorted(candidates, key=lambda size: (abs(size - int(preferred)), size))
        for size in by_distance[: max(1, max_count // 2)]:
            selected.add(int(size))

    remaining = [size for size in candidates if size not in selected]
    needed = max_count - len(selected)
    if needed > 0 and remaining:
        if needed >= len(remaining):
            selected.update(remaining)
        else:
            indexes = np.linspace(0, len(remaining) - 1, needed).astype(int)
            for index in indexes.tolist():
                selected.add(int(remaining[index]))

    compressed = sorted(selected)
    if not compressed:
        return [int(candidates[len(candidates) // 2])]
    return compressed


def _fallback_size(candidates: list[int], preferred: int | None) -> int:
    if not candidates:
        return 0

    if preferred is None:
        return int(candidates[len(candidates) // 2])

    return int(min(candidates, key=lambda size: (abs(size - int(preferred)), size)))


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image

    if image.shape[2] == 1:
        return image[:, :, 0]

    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _gray_variants(gray: np.ndarray) -> dict[str, np.ndarray]:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blurred = cv2.GaussianBlur(clahe, (5, 5), 0)
    return {
        "gray": gray,
        "clahe": clahe,
        "blurred": blurred,
    }


def _adaptive_block_sizes(axis: int) -> list[int]:
    min_axis = max(1, int(axis))
    raw_sizes = [
        int(round(min_axis * 0.025)),
        int(round(min_axis * 0.035)),
        int(round(min_axis * 0.05)),
    ]

    normalized: list[int] = []
    seen: set[int] = set()
    for raw_size in raw_sizes:
        block = max(11, int(raw_size))
        if block % 2 == 0:
            block += 1
        if block >= min_axis:
            block = min_axis - 1
            if block % 2 == 0:
                block -= 1
        if block < 11:
            continue
        if block in seen:
            continue
        seen.add(block)
        normalized.append(block)

    if not normalized:
        fallback = min_axis - 1
        if fallback % 2 == 0:
            fallback -= 1
        if fallback >= 3:
            normalized.append(fallback)

    return normalized


def _projection_min_signal(projection: np.ndarray, axis_length: int, board_size: int) -> float:
    expected_line_count = max(3, int(board_size) + 1)
    base_signal = 255.0 * max(4.0, axis_length / max(8.0, float(expected_line_count) * 2.8))
    percentile_signal = float(np.percentile(projection, 94)) if projection.size else 0.0
    return max(base_signal * 0.24, percentile_signal * 0.4)


def _normalize_lines(lines: list[int], *, axis_length: int) -> list[int] | None:
    if len(lines) < 2 or axis_length <= 2:
        return None

    normalized = [max(0, min(axis_length - 1, int(value))) for value in lines]
    for index in range(1, len(normalized)):
        if normalized[index] <= normalized[index - 1]:
            return None

    return normalized


def _grid_quality_metrics(
    *,
    row_lines: list[int],
    col_lines: list[int],
    height: int,
    width: int,
    board_size: int,
    min_cell_size: int,
    min_coverage_ratio: float,
) -> dict[str, float]:
    row_steps = np.diff(np.array(row_lines, dtype=np.float32))
    col_steps = np.diff(np.array(col_lines, dtype=np.float32))

    if row_steps.size != board_size or col_steps.size != board_size:
        return {
            "quality_score": float("-inf"),
            "coverage_ratio": 0.0,
            "row_step_cv": 1.0,
            "col_step_cv": 1.0,
            "square_delta": 1.0,
            "center_offset": 1.0,
        }

    mean_row = float(np.mean(row_steps))
    mean_col = float(np.mean(col_steps))
    if mean_row <= 0.0 or mean_col <= 0.0:
        return {
            "quality_score": float("-inf"),
            "coverage_ratio": 0.0,
            "row_step_cv": 1.0,
            "col_step_cv": 1.0,
            "square_delta": 1.0,
            "center_offset": 1.0,
        }

    row_step_cv = float(np.std(row_steps) / max(1e-6, mean_row))
    col_step_cv = float(np.std(col_steps) / max(1e-6, mean_col))

    row_span = float(row_lines[-1] - row_lines[0])
    col_span = float(col_lines[-1] - col_lines[0])
    coverage_ratio = float(min(row_span / max(1.0, float(height - 1)), col_span / max(1.0, float(width - 1))))

    square_delta = abs(mean_row - mean_col) / max(1.0, mean_row, mean_col)

    center_x = (col_lines[0] + col_lines[-1]) / 2.0
    center_y = (row_lines[0] + row_lines[-1]) / 2.0
    center_distance = float(np.hypot(center_x - (width / 2.0), center_y - (height / 2.0)))
    center_offset = center_distance / max(1.0, float(np.hypot(width / 2.0, height / 2.0)))

    score = 0.0
    score += coverage_ratio * 1700.0
    score -= (row_step_cv + col_step_cv) * 1100.0
    score -= square_delta * 1500.0
    score -= center_offset * 220.0

    coverage_floor = max(0.1, float(min_coverage_ratio))
    if coverage_ratio < coverage_floor:
        score -= (coverage_floor - coverage_ratio) * 3600.0
    elif coverage_ratio > 1.04:
        score -= (coverage_ratio - 1.04) * 1200.0

    min_cell = max(4.0, float(min_cell_size))
    if mean_row < min_cell:
        score -= (min_cell - mean_row) * 75.0
    if mean_col < min_cell:
        score -= (min_cell - mean_col) * 75.0

    return {
        "quality_score": float(score),
        "coverage_ratio": float(coverage_ratio),
        "row_step_cv": float(row_step_cv),
        "col_step_cv": float(col_step_cv),
        "square_delta": float(square_delta),
        "center_offset": float(center_offset),
    }


def _uniform_pixel_lines(axis_length: int, board_size: int) -> list[int]:
    axis = max(2, int(axis_length))
    size = max(2, int(board_size))
    lines = np.rint(np.linspace(0, axis - 1, size + 1)).astype(int)
    normalized = [int(value) for value in lines.tolist()]

    for index in range(1, len(normalized)):
        normalized[index] = max(normalized[index], normalized[index - 1] + 1)

    if normalized[-1] >= axis:
        shift = normalized[-1] - (axis - 1)
        normalized = [max(0, int(value - shift)) for value in normalized]

    return normalized


def _bbox_from_lines(row_lines: list[int], col_lines: list[int]) -> dict[str, int] | None:
    if len(row_lines) < 2 or len(col_lines) < 2:
        return None

    x1 = int(col_lines[0])
    y1 = int(row_lines[0])
    x2 = int(col_lines[-1])
    y2 = int(row_lines[-1])

    if x2 <= x1 or y2 <= y1:
        return None

    return {
        "x": int(x1),
        "y": int(y1),
        "width": int(x2 - x1 + 1),
        "height": int(y2 - y1 + 1),
    }
