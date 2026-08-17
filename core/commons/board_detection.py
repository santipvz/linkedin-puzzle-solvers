from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class BoardBBox:
    """Image-relative half-open board rectangle."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Board bounding box dimensions must be positive.")

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @classmethod
    def full_image(cls, image: np.ndarray) -> BoardBBox:
        if image.ndim < 2 or image.shape[0] <= 0 or image.shape[1] <= 0:
            raise ValueError("Image must have positive width and height.")
        return cls(x=0, y=0, width=int(image.shape[1]), height=int(image.shape[0]))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> BoardBBox:
        try:
            return cls(
                x=int(value["x"]),
                y=int(value["y"]),
                width=int(value["width"]),
                height=int(value["height"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid board bounding box payload.") from exc

    def clipped_to(self, image: np.ndarray) -> BoardBBox | None:
        if image.ndim < 2:
            raise ValueError("Image must have at least two dimensions.")
        image_height, image_width = image.shape[:2]
        x1 = max(0, self.x)
        y1 = max(0, self.y)
        x2 = min(int(image_width), self.x2)
        y2 = min(int(image_height), self.y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return BoardBBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)

    def inset(self, pixels: int) -> BoardBBox | None:
        amount = max(0, int(pixels))
        width = self.width - amount * 2
        height = self.height - amount * 2
        if width <= 0 or height <= 0:
            return None
        return BoardBBox(self.x + amount, self.y + amount, width, height)

    def to_payload(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class GridBounds:
    """Crop-relative half-open row and column boundaries."""

    rows: tuple[int, ...]
    cols: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.rows) < 2 or len(self.rows) != len(self.cols):
            raise ValueError("Grid axes must contain the same number of boundaries.")
        if self.rows[0] != 0 or self.cols[0] != 0:
            raise ValueError("Grid boundaries must start at zero.")
        if any(right <= left for left, right in zip(self.rows, self.rows[1:])):
            raise ValueError("Row boundaries must be strictly increasing.")
        if any(right <= left for left, right in zip(self.cols, self.cols[1:])):
            raise ValueError("Column boundaries must be strictly increasing.")

    @property
    def board_size(self) -> int:
        return len(self.rows) - 1

    def cells(self) -> tuple[tuple[tuple[int, int, int, int], ...], ...]:
        return tuple(
            tuple(
                (
                    self.cols[col],
                    self.rows[row],
                    self.cols[col + 1] - self.cols[col],
                    self.rows[row + 1] - self.rows[row],
                )
                for col in range(self.board_size)
            )
            for row in range(self.board_size)
        )

    def to_payload(self) -> dict[str, list[int]]:
        return {"rows": list(self.rows), "cols": list(self.cols)}


@dataclass(frozen=True, slots=True)
class ContourBBoxCandidate:
    bbox: BoardBBox
    bbox_area: int
    area_ratio: float
    contour_area: float
    fill_ratio: float
    aspect_ratio: float
    center_distance: float
    touches_edge: bool


@dataclass(frozen=True, slots=True)
class AxisProjections:
    rows: np.ndarray
    cols: np.ndarray


def load_bgr_image(image_path: str | Path) -> np.ndarray:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")
    return image


def crop_board(
    image: np.ndarray,
    bbox: BoardBBox,
    *,
    inset_pixels: int = 0,
    min_width: int = 1,
    min_height: int = 1,
) -> tuple[np.ndarray, BoardBBox] | None:
    clipped = bbox.clipped_to(image)
    if clipped is None:
        return None
    actual = clipped.inset(inset_pixels)
    if actual is None or actual.width < min_width or actual.height < min_height:
        return None
    return image[actual.y : actual.y2, actual.x : actual.x2], actual


def uniform_grid_bounds(*, width: int, height: int, board_size: int) -> GridBounds:
    size = int(board_size)
    if size <= 0:
        raise ValueError("Board size must be positive.")
    if width < size or height < size:
        raise ValueError("Board dimensions must be at least as large as the board size.")
    rows = tuple(int(value) for value in np.rint(np.linspace(0, height, size + 1)))
    cols = tuple(int(value) for value in np.rint(np.linspace(0, width, size + 1)))
    return GridBounds(rows=rows, cols=cols)


def external_contour_bbox_candidates(mask: np.ndarray) -> tuple[ContourBBoxCandidate, ...]:
    if mask.ndim != 2 or mask.size == 0:
        raise ValueError("Contour mask must be a non-empty two-dimensional array.")
    binary = np.asarray(mask, dtype=np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_height, image_width = binary.shape
    image_area = max(1, image_height * image_width)
    image_center_x = image_width / 2
    image_center_y = image_height / 2
    candidates: list[ContourBBoxCandidate] = []

    for contour in contours:
        x, y, width, height = (int(value) for value in cv2.boundingRect(contour))
        if width <= 0 or height <= 0:
            continue
        bbox = BoardBBox(x=x, y=y, width=width, height=height)
        bbox_area = width * height
        contour_area = float(cv2.contourArea(contour))
        center_distance = float(
            np.hypot(x + width / 2 - image_center_x, y + height / 2 - image_center_y)
        )
        candidates.append(
            ContourBBoxCandidate(
                bbox=bbox,
                bbox_area=bbox_area,
                area_ratio=bbox_area / image_area,
                contour_area=contour_area,
                fill_ratio=contour_area / bbox_area,
                aspect_ratio=width / height,
                center_distance=center_distance,
                touches_edge=x == 0 or y == 0 or x + width == image_width or y + height == image_height,
            )
        )

    return tuple(candidates)


def morphological_line_projections(
    binary: np.ndarray,
    *,
    horizontal_kernel_length: int,
    vertical_kernel_length: int,
) -> AxisProjections:
    if binary.ndim != 2 or binary.size == 0:
        raise ValueError("Line mask must be a non-empty two-dimensional array.")
    horizontal_length = max(1, int(horizontal_kernel_length))
    vertical_length = max(1, int(vertical_kernel_length))
    horizontal = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_length, 1)),
    )
    vertical = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_length)),
    )
    return AxisProjections(rows=horizontal.sum(axis=1), cols=vertical.sum(axis=0))
