from __future__ import annotations

from .errors import InvalidBoard
from .models import JsonDict


SUDOKU_SIZE = 6


def validate_sudoku_board(payload: object) -> JsonDict:
    """Validate a Mini Sudoku read from the page: the preset digits, 0 for blanks."""
    if not isinstance(payload, dict) or set(payload) != {"board"}:
        raise InvalidBoard("Mini Sudoku page data must contain only board.")
    board = payload["board"]
    if (not isinstance(board, list) or len(board) != SUDOKU_SIZE
            or any(not isinstance(row, list) or len(row) != SUDOKU_SIZE for row in board)):
        raise InvalidBoard(f"Mini Sudoku boards must be {SUDOKU_SIZE}x{SUDOKU_SIZE}.")
    if any(type(value) is not int or not 0 <= value <= SUDOKU_SIZE for row in board for value in row):
        raise InvalidBoard(f"Mini Sudoku cells must be digits 1 through {SUDOKU_SIZE}, or 0 when blank.")
    if not any(value for row in board for value in row):
        raise InvalidBoard("Mini Sudoku page data has no preset digits.")
    return {"board": [list(row) for row in board]}
