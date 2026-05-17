"""Shared deterministic helpers used across game parsers."""

from .board_detection import (
    BoardGeometry,
    build_grid_coords_from_bounds,
    build_uniform_slice_bounds,
    crop_to_bbox,
    detect_board_geometry,
    infer_candidate_board_sizes,
    to_slice_bounds,
)

__all__ = [
    "BoardGeometry",
    "build_grid_coords_from_bounds",
    "build_uniform_slice_bounds",
    "crop_to_bbox",
    "detect_board_geometry",
    "infer_candidate_board_sizes",
    "to_slice_bounds",
]
