from __future__ import annotations

import numpy as np

from core.vision import extract_line_groups, select_regular_line_subset


def test_extract_line_groups_returns_contiguous_spans_and_strength() -> None:
    projection = np.array([0, 4, 5, 0, 0, 7, 8, 9, 0], dtype=np.float32)

    assert extract_line_groups(projection, 3) == [(1, 2, 9.0), (5, 7, 24.0)]


def test_select_regular_line_subset_ignores_irregular_noise() -> None:
    groups = [
        (0, 0, 10.0),
        (10, 10, 10.0),
        (20, 20, 10.0),
        (30, 30, 10.0),
        (17, 17, 20.0),
    ]

    lines, _ = select_regular_line_subset(groups, 4, strongest_limit=5, min_step=5)

    assert lines == [0, 10, 20, 30]
