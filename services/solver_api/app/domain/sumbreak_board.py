from __future__ import annotations

from .errors import InvalidBoard
from .models import JsonDict


MIN_SIDE = 2
MAX_SIDE = 8
MAX_TILE_VALUE = 1 << 24


def validate_sumbreak_board(payload: object) -> JsonDict:
    """Validate the tile values read from the page before they reach a worker."""
    if not isinstance(payload, dict) or set(payload) != {"board"}:
        raise InvalidBoard("Sumbreak page data must contain only a board.")
    board = payload["board"]
    if not isinstance(board, list) or not MIN_SIDE <= len(board) <= MAX_SIDE:
        raise InvalidBoard(f"Sumbreak boards must have {MIN_SIDE} through {MAX_SIDE} rows.")
    columns = len(board[0]) if isinstance(board[0], list) else 0
    if not MIN_SIDE <= columns <= MAX_SIDE:
        raise InvalidBoard(f"Sumbreak boards must have {MIN_SIDE} through {MAX_SIDE} columns.")
    tiles = 0
    for row in board:
        if not isinstance(row, list) or len(row) != columns:
            raise InvalidBoard("Sumbreak page data must have a rectangular board.")
        for value in row:
            if value is None:
                continue
            if type(value) is not int or not 1 <= value <= MAX_TILE_VALUE:
                raise InvalidBoard("Sumbreak cells must be positive integers or null for empty cells.")
            tiles += 1
    if tiles == 0:
        raise InvalidBoard("Sumbreak page data has no tiles.")
    return {"board": [list(row) for row in board]}
