"""Shared deterministic helpers used across game parsers."""

from .board_detection import (
    AxisProjections,
    BoardBBox,
    ContourBBoxCandidate,
    GridBounds,
    crop_board,
    external_contour_bbox_candidates,
    load_bgr_image,
    morphological_line_projections,
    uniform_grid_bounds,
)

__all__ = [
    "AxisProjections",
    "BoardBBox",
    "ContourBBoxCandidate",
    "GridBounds",
    "crop_board",
    "external_contour_bbox_candidates",
    "load_bgr_image",
    "morphological_line_projections",
    "uniform_grid_bounds",
]
