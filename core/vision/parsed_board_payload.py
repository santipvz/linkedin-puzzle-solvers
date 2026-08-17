from __future__ import annotations

from typing import Any, Mapping, TypedDict

from core.commons.board_detection import BoardBBox, GridBounds


class BoardBBoxPayload(TypedDict):
    x: int
    y: int
    width: int
    height: int


class GridLinesPayload(TypedDict):
    rows: list[int]
    cols: list[int]


def normalize_board_bbox(board_bbox: BoardBBox | Mapping[str, object]) -> BoardBBoxPayload:
    normalized = board_bbox if isinstance(board_bbox, BoardBBox) else BoardBBox.from_mapping(board_bbox)
    return normalized.to_payload()


def build_grid_lines_payload(grid: GridBounds) -> GridLinesPayload:
    return grid.to_payload()


def build_parsed_board_payload(
    *,
    board_size: int,
    board_bbox: BoardBBox | Mapping[str, object],
    grid: GridBounds,
    include_legacy_size: bool = False,
    extra_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if int(board_size) != grid.board_size:
        raise ValueError("Board size does not match grid dimensions.")
    payload: dict[str, Any] = {
        "board_size": int(board_size),
        "board_bbox": normalize_board_bbox(board_bbox),
        "grid_lines": build_grid_lines_payload(grid),
    }

    if include_legacy_size:
        payload["size"] = int(board_size)

    if extra_fields:
        reserved = payload.keys() & extra_fields.keys()
        if reserved:
            raise ValueError(f"Cannot overwrite parsed board fields: {', '.join(sorted(reserved))}")
        payload.update(dict(extra_fields))

    return payload
