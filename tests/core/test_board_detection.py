from __future__ import annotations

import cv2
import numpy as np
import pytest

from core.commons import BoardBBox, crop_board, external_contour_bbox_candidates, uniform_grid_bounds


def test_crop_board_clips_using_original_bbox_edges() -> None:
    image = np.arange(100, dtype=np.uint8).reshape(10, 10)

    cropped = crop_board(image, BoardBBox(x=-2, y=-3, width=6, height=8))

    assert cropped is not None
    crop, bbox = cropped
    assert bbox == BoardBBox(x=0, y=0, width=4, height=5)
    assert crop.shape == (5, 4)
    assert np.array_equal(crop, image[:5, :4])


def test_crop_board_rejects_outside_collapsed_and_tiny_boxes() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)

    assert crop_board(image, BoardBBox(20, 20, 2, 2)) is None
    assert crop_board(image, BoardBBox(1, 1, 4, 4), inset_pixels=2) is None
    assert crop_board(image, BoardBBox(1, 1, 5, 5), min_width=6) is None


@pytest.mark.parametrize("width,height,size", [(12, 12, 3), (13, 11, 5), (8, 7, 7)])
def test_uniform_grid_bounds_cover_crop_without_gaps(width: int, height: int, size: int) -> None:
    grid = uniform_grid_bounds(width=width, height=height, board_size=size)

    assert grid.board_size == size
    assert grid.rows[0] == grid.cols[0] == 0
    assert grid.rows[-1] == height
    assert grid.cols[-1] == width
    assert len(grid.cells()) == size
    assert all(len(row) == size for row in grid.cells())
    assert sum(cell[2] for cell in grid.cells()[0]) == width
    assert sum(row[0][3] for row in grid.cells()) == height


def test_uniform_grid_bounds_reject_invalid_dimensions() -> None:
    with pytest.raises(ValueError):
        uniform_grid_bounds(width=4, height=4, board_size=5)


def test_contour_candidates_measure_geometry_without_selecting_policy() -> None:
    mask = np.zeros((100, 120), dtype=np.uint8)
    cv2.rectangle(mask, (20, 10), (79, 69), 255, thickness=-1)

    candidates = external_contour_bbox_candidates(mask)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.bbox == BoardBBox(20, 10, 60, 60)
    assert candidate.bbox_area == 3600
    assert candidate.aspect_ratio == pytest.approx(1.0)
    assert 0.9 < candidate.fill_ratio <= 1.0
    assert not candidate.touches_edge
