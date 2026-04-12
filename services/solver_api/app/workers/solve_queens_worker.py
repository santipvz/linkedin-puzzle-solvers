from __future__ import annotations

import contextlib
import importlib
import io
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

try:
    from .common import activate_game_import_context, game_root_for_worker, run_worker_cli
except ImportError:
    from common import activate_game_import_context, game_root_for_worker, run_worker_cli


MIN_BOARD_AREA_RATIO = 0.08
DARK_PIXEL_THRESHOLD = 72


def _serialize_solution_grid(solution: Any) -> list[list[int]]:
    return [[int(value) for value in row] for row in solution.tolist()]


def _write_temp_image(image: np.ndarray, prefix: str) -> Path | None:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix=prefix)
    handle.close()

    ok = cv2.imwrite(handle.name, image)
    if not ok:
        Path(handle.name).unlink(missing_ok=True)
        return None

    return Path(handle.name)


def _build_contour_masks(image: np.ndarray) -> list[np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, dark_mask = cv2.threshold(gray, 92, 255, cv2.THRESH_BINARY_INV)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 130)

    kernel = np.ones((3, 3), np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    edge_mask = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    edge_mask = cv2.dilate(edge_mask, kernel, iterations=1)

    return [dark_mask, edge_mask]


def _select_best_bbox(contours: Sequence[Any], image_width: int, image_height: int) -> tuple[int, int, int, int] | None:
    image_area = image_width * image_height
    center_x = image_width / 2
    center_y = image_height / 2

    best_score = float("-inf")
    best_bbox: tuple[int, int, int, int] | None = None

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width <= 0 or height <= 0:
            continue

        bbox_area = width * height
        if bbox_area < image_area * MIN_BOARD_AREA_RATIO:
            continue

        aspect_ratio = width / height
        if not (0.78 <= aspect_ratio <= 1.22):
            continue

        contour_area = cv2.contourArea(contour)
        fill_ratio = contour_area / max(bbox_area, 1)
        if fill_ratio < 0.35:
            continue

        contour_center_x = x + width / 2
        contour_center_y = y + height / 2
        center_distance = float(np.hypot(contour_center_x - center_x, contour_center_y - center_y))

        touches_edge = x <= 1 or y <= 1 or x + width >= image_width - 1 or y + height >= image_height - 1
        edge_touch_penalty = 0.96 if touches_edge else 1.0

        score = (bbox_area * fill_ratio * edge_touch_penalty) - (center_distance * 220)
        if score > best_score:
            best_score = score
            best_bbox = (x, y, width, height)

    return best_bbox


def _extract_board_crop(image: np.ndarray) -> tuple[np.ndarray, dict[str, int]] | tuple[None, None]:
    image_height, image_width = image.shape[:2]
    masks = _build_contour_masks(image)

    best_bbox: tuple[int, int, int, int] | None = None
    best_area = -1

    for mask in masks:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bbox = _select_best_bbox(contours, image_width, image_height)
        if bbox is None:
            continue

        _, _, width, height = bbox
        area = width * height
        if area > best_area:
            best_area = area
            best_bbox = bbox

    if best_bbox is None:
        return None, None

    x, y, width, height = best_bbox
    inner_trim = max(1, int(min(width, height) * 0.003))

    x1 = max(0, x + inner_trim)
    y1 = max(0, y + inner_trim)
    x2 = min(image_width, x + width - inner_trim)
    y2 = min(image_height, y + height - inner_trim)

    if x2 - x1 < 120 or y2 - y1 < 120:
        return None, None

    crop = image[y1:y2, x1:x2]
    metadata = {
        "x": int(x1),
        "y": int(y1),
        "width": int(x2 - x1),
        "height": int(y2 - y1),
    }
    return crop, metadata


def _prepare_queens_image(image_path: Path) -> tuple[Path | None, dict[str, int] | None]:
    image = cv2.imread(str(image_path))
    if image is None:
        return None, None

    crop, metadata = _extract_board_crop(image)
    if crop is None or metadata is None:
        return None, None

    temp_path = _write_temp_image(crop, "queens_crop_")
    if temp_path is None:
        return None, None

    return temp_path, metadata


def _detect_board_geometry(
    image: np.ndarray,
    board_detector_class: Any,
) -> tuple[int, list[int], list[int]] | tuple[None, None, None]:
    detector = board_detector_class()

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        board_size = int(detector.detect_board_size(image))

    if board_size <= 0:
        return None, None, None

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        horizontal_lines, vertical_lines = detector.detect_grid(image, board_size)

    if len(horizontal_lines) < board_size + 1 or len(vertical_lines) < board_size + 1:
        return None, None, None

    return board_size, horizontal_lines, vertical_lines


def _build_icon_mask(
    image: np.ndarray,
    board_size: int,
    horizontal_lines: Sequence[int],
    vertical_lines: Sequence[int],
) -> np.ndarray:
    image_height, image_width = image.shape[:2]
    mask = np.zeros((image_height, image_width), dtype=np.uint8)

    for row in range(board_size):
        for col in range(board_size):
            y1 = int(horizontal_lines[row])
            y2 = int(horizontal_lines[row + 1])
            x1 = int(vertical_lines[col])
            x2 = int(vertical_lines[col + 1])

            y1 = max(0, min(y1, image_height - 1))
            x1 = max(0, min(x1, image_width - 1))
            y2 = max(y1 + 1, min(y2, image_height))
            x2 = max(x1 + 1, min(x2, image_width))

            cell_height = y2 - y1
            cell_width = x2 - x1
            if cell_height < 12 or cell_width < 12:
                continue

            inner_margin = max(2, min(cell_height, cell_width) // 8)
            iy1 = y1 + inner_margin
            iy2 = y2 - inner_margin
            ix1 = x1 + inner_margin
            ix2 = x2 - inner_margin

            if iy2 <= iy1 or ix2 <= ix1:
                continue

            roi = image[iy1:iy2, ix1:ix2]
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            local_cutoff = min(DARK_PIXEL_THRESHOLD, int(np.percentile(gray_roi, 20)))
            dark = (gray_roi <= local_cutoff).astype(np.uint8) * 255

            if int(np.count_nonzero(dark)) < 10:
                continue

            dark = cv2.medianBlur(dark, 3)
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)

            min_area = max(12, (roi.shape[0] * roi.shape[1]) // 260)
            max_area = max(40, (roi.shape[0] * roi.shape[1]) // 3)

            for label in range(1, num_labels):
                area = int(stats[label, cv2.CC_STAT_AREA])
                if area < min_area or area > max_area:
                    continue

                lx = int(stats[label, cv2.CC_STAT_LEFT])
                ly = int(stats[label, cv2.CC_STAT_TOP])
                lw = int(stats[label, cv2.CC_STAT_WIDTH])
                lh = int(stats[label, cv2.CC_STAT_HEIGHT])
                cx = lx + lw / 2
                cy = ly + lh / 2

                if cx < roi.shape[1] * 0.18 or cx > roi.shape[1] * 0.82:
                    continue
                if cy < roi.shape[0] * 0.18 or cy > roi.shape[0] * 0.82:
                    continue

                component_mask = labels == label
                mask[iy1:iy2, ix1:ix2][component_mask] = 255

    return mask


def _prepare_inpainted_image(
    image_path: Path,
    board_detector_class: Any,
) -> tuple[Path | None, dict[str, int] | None]:
    image = cv2.imread(str(image_path))
    if image is None:
        return None, None

    board_size, horizontal_lines, vertical_lines = _detect_board_geometry(image, board_detector_class)
    if board_size is None or horizontal_lines is None or vertical_lines is None:
        return None, None

    icon_mask = _build_icon_mask(image, board_size, horizontal_lines, vertical_lines)
    masked_pixels = int(np.count_nonzero(icon_mask))

    if masked_pixels < 8:
        return None, {
            "board_size": int(board_size),
            "masked_pixels": int(masked_pixels),
        }

    inpainted = cv2.inpaint(image, icon_mask, 3, cv2.INPAINT_TELEA)
    temp_path = _write_temp_image(inpainted, "queens_inpaint_")
    if temp_path is None:
        return None, None

    metadata = {
        "board_size": int(board_size),
        "masked_pixels": int(masked_pixels),
    }
    return temp_path, metadata


def _run_solver_attempt(queens_solver_class: Any, image_path: Path, attempt_label: str) -> dict[str, Any]:
    solver = queens_solver_class(verbose=False)
    captured_logs = io.StringIO()

    with contextlib.redirect_stdout(captured_logs), contextlib.redirect_stderr(captured_logs):
        solved = solver.solve_from_image(
            str(image_path),
            output_dir="",
            filename_prefix="",
            generate_visualizations=False,
            quiet_mode=True,
        )

    puzzle_state = solver.puzzle_state
    solver_result = solver.solver_result

    board_size = int(puzzle_state.board_info.size) if puzzle_state is not None else 0
    regions_detected = int(len(puzzle_state.regions)) if puzzle_state is not None else 0

    solution_grid = None
    moves: list[dict[str, int]] = []

    if puzzle_state is not None and puzzle_state.solution is not None:
        solution_grid = _serialize_solution_grid(puzzle_state.solution)
        for row_index, row_values in enumerate(solution_grid):
            for col_index, value in enumerate(row_values):
                if value == 1:
                    moves.append({"row": row_index, "col": col_index})

    if solver_result is None:
        response = {
            "puzzle": "queens",
            "solved": False,
            "board_size": board_size,
            "moves": [],
            "solution_grid": None,
            "error": "Solver returned no result object.",
            "details": {
                "iterations": 0,
                "execution_time_sec": 0.0,
                "validation_passed": False,
                "regions_detected": regions_detected,
                "attempt": attempt_label,
            },
        }
    else:
        error_message = solver_result.error_message
        if not solved and not error_message:
            error_message = "No valid solution found."

        response = {
            "puzzle": "queens",
            "solved": bool(solved),
            "board_size": board_size,
            "moves": moves,
            "solution_grid": solution_grid,
            "error": error_message,
            "details": {
                "iterations": int(solver_result.iterations),
                "execution_time_sec": float(solver_result.execution_time),
                "validation_passed": bool(solver_result.validation_passed),
                "regions_detected": regions_detected,
                "attempt": attempt_label,
            },
        }

    logs_value = captured_logs.getvalue().strip()
    if logs_value:
        response["logs"] = logs_value[:1200]

    return response


def _attempt_quality(result: dict[str, Any]) -> int:
    details = result.get("details") or {}
    solved = bool(result.get("solved"))
    board_size = int(result.get("board_size") or 0)
    regions_detected = int(details.get("regions_detected") or 0)
    iterations = int(details.get("iterations") or 0)
    mismatch = abs(regions_detected - board_size) if board_size > 0 and regions_detected > 0 else 99
    error_message = str(result.get("error") or "").lower()

    score = 0
    if solved:
        score += 100000

    if board_size > 0:
        score += 1000
        score += board_size * 3

    if details.get("validation_passed"):
        score += 120

    if result.get("solution_grid") is not None:
        score += 30

    score += min(iterations, 5000) // 8
    score -= mismatch * 260

    if "cannot have a valid solution" in error_message:
        score -= 420

    return score


def _select_best_attempt(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    if not attempts:
        return {
            "puzzle": "queens",
            "solved": False,
            "board_size": 0,
            "moves": [],
            "solution_grid": None,
            "error": "No solver attempts were executed.",
            "details": {
                "iterations": 0,
                "execution_time_sec": 0.0,
                "validation_passed": False,
                "regions_detected": 0,
            },
        }

    return max(attempts, key=_attempt_quality)


def solve(image_path: Path) -> dict[str, Any]:
    game_root = game_root_for_worker(__file__, "queen_solver")
    if not game_root.exists():
        return {
            "puzzle": "queens",
            "solved": False,
            "error": "Queens project folder not found.",
        }

    activate_game_import_context(game_root)

    queens_module = importlib.import_module(".".join(["src", "queens_solver"]))
    queens_solver_class = getattr(queens_module, "QueensSolver")

    detector_module = importlib.import_module(".".join(["src", "vision", "board_detector"]))
    board_detector_class = getattr(detector_module, "EdgeDetectionBoardDetector")

    attempts: list[dict[str, Any]] = []
    temp_paths: list[Path] = []
    detected_board_bbox: dict[str, int] | None = None

    try:
        crop_path, crop_metadata = _prepare_queens_image(image_path)
        if crop_path is not None:
            temp_paths.append(crop_path)
            if crop_metadata is not None:
                detected_board_bbox = crop_metadata

            inpainted_crop_path, inpainted_crop_meta = _prepare_inpainted_image(crop_path, board_detector_class)
            if inpainted_crop_path is not None:
                temp_paths.append(inpainted_crop_path)
                inpainted_cropped_attempt = _run_solver_attempt(
                    queens_solver_class,
                    inpainted_crop_path,
                    "auto-cropped-inpainted",
                )
                if crop_metadata is not None:
                    inpainted_cropped_attempt["details"]["crop_bbox"] = crop_metadata
                if inpainted_crop_meta is not None:
                    inpainted_cropped_attempt["details"].update(inpainted_crop_meta)
                attempts.append(inpainted_cropped_attempt)

            cropped_attempt = _run_solver_attempt(queens_solver_class, crop_path, "auto-cropped")
            if crop_metadata is not None:
                cropped_attempt["details"]["crop_bbox"] = crop_metadata
            attempts.append(cropped_attempt)

        inpainted_original_path, inpainted_original_meta = _prepare_inpainted_image(image_path, board_detector_class)
        if inpainted_original_path is not None:
            temp_paths.append(inpainted_original_path)
            inpainted_original_attempt = _run_solver_attempt(
                queens_solver_class,
                inpainted_original_path,
                "original-inpainted",
            )
            if inpainted_original_meta is not None:
                inpainted_original_attempt["details"].update(inpainted_original_meta)
            attempts.append(inpainted_original_attempt)

        original_attempt = _run_solver_attempt(queens_solver_class, image_path, "original")
        attempts.append(original_attempt)

        best_attempt = _select_best_attempt(attempts)

        details = best_attempt.setdefault("details", {})
        if detected_board_bbox is not None:
            details["board_bbox"] = detected_board_bbox
        elif isinstance(details.get("crop_bbox"), dict):
            details["board_bbox"] = details["crop_bbox"]

        details["attempt_count"] = len(attempts)
        details["attempts"] = [
            {
                "attempt": attempt.get("details", {}).get("attempt"),
                "solved": bool(attempt.get("solved")),
                "board_size": int(attempt.get("board_size") or 0),
                "regions_detected": int((attempt.get("details") or {}).get("regions_detected") or 0),
                "iterations": int((attempt.get("details") or {}).get("iterations") or 0),
            }
            for attempt in attempts
        ]

        return best_attempt
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)


def main() -> int:
    return run_worker_cli(
        argv=sys.argv,
        solve_fn=solve,
        worker_script="solve_queens_worker.py",
        worker_label="Queens",
    )


if __name__ == "__main__":
    raise SystemExit(main())
