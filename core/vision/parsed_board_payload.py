from __future__ import annotations

from typing import Any, Iterable, Mapping, TypedDict


class BoardBBoxPayload(TypedDict):
    x: int
    y: int
    width: int
    height: int


class GridLinesPayload(TypedDict):
    rows: list[int]
    cols: list[int]


def normalize_board_bbox(board_bbox: Mapping[str, object]) -> BoardBBoxPayload:
    return {
        "x": int(board_bbox.get("x", 0)),
        "y": int(board_bbox.get("y", 0)),
        "width": int(board_bbox.get("width", 0)),
        "height": int(board_bbox.get("height", 0)),
    }


def build_grid_lines_payload(
    *,
    row_lines: Iterable[object],
    col_lines: Iterable[object],
) -> GridLinesPayload:
    return {
        "rows": [int(value) for value in row_lines],
        "cols": [int(value) for value in col_lines],
    }


def build_parsed_board_payload(
    *,
    board_size: int,
    board_bbox: Mapping[str, object],
    row_lines: Iterable[object],
    col_lines: Iterable[object],
    include_legacy_size: bool = False,
    extra_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "board_size": int(board_size),
        "board_bbox": normalize_board_bbox(board_bbox),
        "grid_lines": build_grid_lines_payload(row_lines=row_lines, col_lines=col_lines),
    }

    if include_legacy_size:
        payload["size"] = int(board_size)

    if extra_fields:
        payload.update(dict(extra_fields))

    return payload
