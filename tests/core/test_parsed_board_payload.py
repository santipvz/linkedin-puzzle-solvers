from __future__ import annotations

import pytest

from core.commons import BoardBBox, uniform_grid_bounds
from core.vision import build_parsed_board_payload


def test_build_parsed_board_payload_uses_canonical_geometry() -> None:
    payload = build_parsed_board_payload(
        board_size=3,
        board_bbox=BoardBBox(4, 5, 30, 33),
        grid=uniform_grid_bounds(width=30, height=33, board_size=3),
        include_legacy_size=True,
        extra_fields={"board": [[0] * 3 for _ in range(3)]},
    )

    assert payload["board_size"] == payload["size"] == 3
    assert payload["board_bbox"] == {"x": 4, "y": 5, "width": 30, "height": 33}
    assert payload["grid_lines"]["rows"] == [0, 11, 22, 33]


def test_build_parsed_board_payload_rejects_reserved_overrides() -> None:
    with pytest.raises(ValueError):
        build_parsed_board_payload(
            board_size=2,
            board_bbox=BoardBBox(0, 0, 10, 10),
            grid=uniform_grid_bounds(width=10, height=10, board_size=2),
            extra_fields={"board_size": 9},
        )
