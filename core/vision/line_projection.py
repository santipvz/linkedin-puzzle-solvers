from __future__ import annotations

import itertools
from typing import Sequence

import numpy as np

LineGroup = tuple[int, int, float]


def extract_line_groups(projection: np.ndarray, min_signal: float) -> list[LineGroup]:
    """Group contiguous indices in a 1D projection that exceed a signal threshold."""
    indices = np.where(projection > min_signal)[0]
    if indices.size == 0:
        return []

    split_indices = np.where(np.diff(indices) > 1)[0] + 1
    chunks = np.split(indices, split_indices)

    groups: list[LineGroup] = []
    for chunk in chunks:
        if chunk.size == 0:
            continue

        start = int(chunk[0])
        end = int(chunk[-1])
        strength = float(np.sum(projection[start : end + 1]))
        groups.append((start, end, strength))

    return groups


def select_regular_line_subset(
    groups: Sequence[LineGroup],
    expected_count: int,
    *,
    strongest_limit: int = 18,
    min_step: int = 10,
    step_std_penalty: float = 30.0,
    step_range_penalty: float = 7.0,
    strength_scale: float = 0.001,
) -> tuple[list[int] | None, float | None]:
    """Pick a near-regular subset of projected line groups."""
    if len(groups) < expected_count:
        return None, None

    strongest = sorted(groups, key=lambda group: group[2], reverse=True)[:strongest_limit]
    strongest = sorted(strongest, key=lambda group: (group[0] + group[1]) // 2)
    if len(strongest) < expected_count:
        return None, None

    best_lines: list[int] | None = None
    best_score: float | None = None

    for combo in itertools.combinations(range(len(strongest)), expected_count):
        lines = [int((strongest[index][0] + strongest[index][1]) // 2) for index in combo]
        steps = np.diff(lines)
        if steps.size != expected_count - 1:
            continue
        if int(np.min(steps)) < min_step:
            continue

        steps_std = float(np.std(steps))
        step_range = float(np.max(steps) - np.min(steps))
        strength = float(sum(strongest[index][2] for index in combo))

        score = strength * strength_scale
        score -= steps_std * step_std_penalty
        score -= step_range * step_range_penalty

        if best_score is None or score > best_score:
            best_score = score
            best_lines = lines

    return best_lines, best_score


def select_span_lines(groups: Sequence[LineGroup], *, strongest_limit: int = 18) -> list[int] | None:
    """Select the pair of projected lines with the largest span."""
    if len(groups) < 2:
        return None

    strongest = sorted(groups, key=lambda group: group[2], reverse=True)[:strongest_limit]
    centers = sorted(int((group[0] + group[1]) // 2) for group in strongest)
    if len(centers) < 2:
        return None

    best_pair: list[int] | None = None
    best_span = -1
    for left_index in range(len(centers) - 1):
        for right_index in range(left_index + 1, len(centers)):
            left = centers[left_index]
            right = centers[right_index]
            span = right - left
            if span > best_span:
                best_span = span
                best_pair = [left, right]

    return best_pair
