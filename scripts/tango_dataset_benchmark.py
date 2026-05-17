#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import cv2


REPO_ROOT = Path(__file__).resolve().parents[1]
TANGO_SRC = REPO_ROOT / "games" / "tango_solver" / "src"
if str(TANGO_SRC) not in sys.path:
    sys.path.insert(0, str(TANGO_SRC))

from image_parser import TangoImageParser


def _safe_mean(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def _safe_median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _safe_min(values: list[float]) -> float:
    return float(min(values)) if values else 0.0


def _safe_max(values: list[float]) -> float:
    return float(max(values)) if values else 0.0


def _load_expected_counts(json_path: Path) -> tuple[int | None, int | None]:
    if not json_path.exists():
        return None, None

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    details = payload.get("details") if isinstance(payload, dict) else None
    if not isinstance(details, dict):
        return None, None

    fixed_count = details.get("fixed_count")
    constraint_count = details.get("constraint_count")

    fixed_expected = int(fixed_count) if isinstance(fixed_count, (int, float)) else None
    constraint_expected = int(constraint_count) if isinstance(constraint_count, (int, float)) else None
    return fixed_expected, constraint_expected


def run_benchmark(dataset_root: Path, limit: int | None, min_area_ratio: float, print_worst: int) -> dict[str, Any]:
    parser = TangoImageParser()
    image_paths = sorted(dataset_root.glob("*/*.png"))
    if limit is not None and limit > 0:
        image_paths = image_paths[:limit]

    total = len(image_paths)
    parsed = 0

    area_ratios: list[float] = []
    grid_quality_scores: list[float] = []
    fixed_abs_errors: list[float] = []
    constraint_abs_errors: list[float] = []

    small_bbox_cases: list[dict[str, Any]] = []
    parse_failures: list[str] = []
    worst_fixed_cases: list[dict[str, Any]] = []
    worst_constraint_cases: list[dict[str, Any]] = []

    for image_path in image_paths:
        img = cv2.imread(str(image_path))
        if img is None:
            parse_failures.append(f"{image_path}: could not read image")
            continue

        height, width = img.shape[:2]
        state = parser.parse_image(str(image_path))
        if not state:
            parse_failures.append(f"{image_path}: parse_image returned None")
            continue

        parsed += 1

        bbox = state.get("board_bbox") if isinstance(state, dict) else None
        if isinstance(bbox, dict):
            bbox_width = float(bbox.get("width") or width)
            bbox_height = float(bbox.get("height") or height)
        else:
            bbox_width = float(width)
            bbox_height = float(height)

        area_ratio = (bbox_width * bbox_height) / max(1.0, float(width * height))
        area_ratios.append(area_ratio)

        if area_ratio < min_area_ratio:
            small_bbox_cases.append(
                {
                    "path": str(image_path.relative_to(REPO_ROOT)),
                    "area_ratio": area_ratio,
                    "bbox": bbox,
                    "image_size": (int(width), int(height)),
                    "board_detection": state.get("board_detection"),
                    "grid_detection": state.get("grid_detection"),
                }
            )

        grid_detection = state.get("grid_detection") if isinstance(state, dict) else None
        if isinstance(grid_detection, dict):
            grid_quality = grid_detection.get("quality_score")
            if isinstance(grid_quality, (int, float)):
                grid_quality_scores.append(float(grid_quality))

        fixed_detected = len(state.get("fixed_pieces", []))
        constraints_detected = len(state.get("constraints", []))

        expected_fixed, expected_constraints = _load_expected_counts(image_path.with_suffix(".json"))

        if expected_fixed is not None:
            fixed_error = abs(fixed_detected - expected_fixed)
            fixed_abs_errors.append(float(fixed_error))
            worst_fixed_cases.append(
                {
                    "path": str(image_path.relative_to(REPO_ROOT)),
                    "detected": int(fixed_detected),
                    "expected": int(expected_fixed),
                    "abs_error": int(fixed_error),
                }
            )

        if expected_constraints is not None:
            constraint_error = abs(constraints_detected - expected_constraints)
            constraint_abs_errors.append(float(constraint_error))
            worst_constraint_cases.append(
                {
                    "path": str(image_path.relative_to(REPO_ROOT)),
                    "detected": int(constraints_detected),
                    "expected": int(expected_constraints),
                    "abs_error": int(constraint_error),
                }
            )

    worst_fixed_cases.sort(key=lambda item: item["abs_error"], reverse=True)
    worst_constraint_cases.sort(key=lambda item: item["abs_error"], reverse=True)

    return {
        "total": total,
        "parsed": parsed,
        "parse_rate": (parsed / total) if total else 0.0,
        "area_ratios": area_ratios,
        "grid_quality_scores": grid_quality_scores,
        "fixed_abs_errors": fixed_abs_errors,
        "constraint_abs_errors": constraint_abs_errors,
        "small_bbox_cases": small_bbox_cases,
        "parse_failures": parse_failures,
        "worst_fixed_cases": worst_fixed_cases[:print_worst],
        "worst_constraint_cases": worst_constraint_cases[:print_worst],
    }


def print_report(result: dict[str, Any], min_area_ratio: float) -> None:
    print("Tango dataset benchmark")
    print("=" * 80)
    print(f"Total images          : {result['total']}")
    print(f"Parsed successfully   : {result['parsed']} ({result['parse_rate'] * 100:.2f}%)")
    print(f"Small bbox (<{min_area_ratio:.2f}) : {len(result['small_bbox_cases'])}")

    area_ratios = result["area_ratios"]
    if area_ratios:
        print(
            "Board area ratio      : "
            f"min={_safe_min(area_ratios):.3f} "
            f"med={_safe_median(area_ratios):.3f} "
            f"mean={_safe_mean(area_ratios):.3f} "
            f"max={_safe_max(area_ratios):.3f}"
        )

    grid_quality_scores = result["grid_quality_scores"]
    if grid_quality_scores:
        print(
            "Grid quality score    : "
            f"min={_safe_min(grid_quality_scores):.2f} "
            f"med={_safe_median(grid_quality_scores):.2f} "
            f"mean={_safe_mean(grid_quality_scores):.2f} "
            f"max={_safe_max(grid_quality_scores):.2f}"
        )

    fixed_abs_errors = result["fixed_abs_errors"]
    if fixed_abs_errors:
        print(
            "Fixed count abs error : "
            f"med={_safe_median(fixed_abs_errors):.2f} "
            f"mean={_safe_mean(fixed_abs_errors):.2f} "
            f"max={_safe_max(fixed_abs_errors):.2f}"
        )

    constraint_abs_errors = result["constraint_abs_errors"]
    if constraint_abs_errors:
        print(
            "Constraint abs error  : "
            f"med={_safe_median(constraint_abs_errors):.2f} "
            f"mean={_safe_mean(constraint_abs_errors):.2f} "
            f"max={_safe_max(constraint_abs_errors):.2f}"
        )

    if result["parse_failures"]:
        print("\nParse failures:")
        for failure in result["parse_failures"]:
            print(f"- {failure}")

    if result["small_bbox_cases"]:
        print("\nSmall bbox cases:")
        for case in result["small_bbox_cases"]:
            print(
                f"- {case['path']} area_ratio={case['area_ratio']:.3f} "
                f"board_detection={case['board_detection']}"
            )

    if result["worst_fixed_cases"]:
        print("\nWorst fixed-count cases:")
        for case in result["worst_fixed_cases"]:
            print(
                f"- {case['path']} detected={case['detected']} "
                f"expected={case['expected']} abs_error={case['abs_error']}"
            )

    if result["worst_constraint_cases"]:
        print("\nWorst constraint-count cases:")
        for case in result["worst_constraint_cases"]:
            print(
                f"- {case['path']} detected={case['detected']} "
                f"expected={case['expected']} abs_error={case['abs_error']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Tango parser over datasets/tango PNG samples")
    parser.add_argument(
        "--dataset-root",
        default="datasets/tango",
        help="Path to Tango dataset root containing date subfolders",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of images to evaluate",
    )
    parser.add_argument(
        "--min-area-ratio",
        type=float,
        default=0.55,
        help="Flag bboxes with area ratio below this threshold",
    )
    parser.add_argument(
        "--print-worst",
        type=int,
        default=8,
        help="Number of worst fixed/constraint mismatch cases to print",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code when benchmark quality gates are not met",
    )
    args = parser.parse_args()

    dataset_root = (REPO_ROOT / args.dataset_root).resolve()
    if not dataset_root.exists():
        print(f"Dataset root not found: {dataset_root}", file=sys.stderr)
        return 2

    result = run_benchmark(
        dataset_root=dataset_root,
        limit=args.limit,
        min_area_ratio=float(args.min_area_ratio),
        print_worst=max(1, int(args.print_worst)),
    )

    print_report(result, min_area_ratio=float(args.min_area_ratio))

    if not args.strict:
        return 0

    parse_rate = float(result["parse_rate"])
    fixed_mae = _safe_mean(result["fixed_abs_errors"])
    constraint_mae = _safe_mean(result["constraint_abs_errors"])
    small_bbox_count = int(len(result["small_bbox_cases"]))

    strict_failures: list[str] = []
    if parse_rate < 0.95:
        strict_failures.append(f"parse_rate={parse_rate:.3f} < 0.95")
    if fixed_mae > 2.0:
        strict_failures.append(f"fixed_mae={fixed_mae:.2f} > 2.0")
    if constraint_mae > 2.0:
        strict_failures.append(f"constraint_mae={constraint_mae:.2f} > 2.0")
    if small_bbox_count > 0:
        strict_failures.append(f"small_bbox_count={small_bbox_count} > 0")

    if strict_failures:
        print("\nStrict benchmark gates failed:")
        for item in strict_failures:
            print(f"- {item}")
        return 1

    print("\nStrict benchmark gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
