from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from .workers.common import BoardBBox, JsonValue


PuzzleKey = Literal["queens", "tango", "sudoku", "zip", "patches"]


class GridCell(TypedDict):
    row: int
    col: int


class Move(GridCell, total=False):
    value: int
    area: int
    top: int
    left: int
    height: int
    width: int
    clue_row: int
    clue_col: int


class ResponseDetails(TypedDict, total=False):
    board_bbox: BoardBBox | None
    parse_reliable: bool
    iterations: int
    steps: int
    clue_count: int
    fixed_count: int
    constraint_count: int
    solution_count: int
    unique_solution: bool
    recovered_clues: list[dict[str, JsonValue]]


class SolverResponse(TypedDict):
    puzzle: PuzzleKey
    solved: bool
    board_size: int
    error: str | None
    details: ResponseDetails
    moves: NotRequired[list[Move]]
    solution_grid: NotRequired[list[list[int]] | None]
    path: NotRequired[list[GridCell]]
    directions: NotRequired[list[str]]
    clues: NotRequired[list[dict[str, JsonValue]]]
    clue_grid: NotRequired[list[list[JsonValue]]]
    fixed_pieces: NotRequired[list[dict[str, JsonValue]]]
    constraints: NotRequired[list[dict[str, JsonValue]]]
    logs: NotRequired[str]
