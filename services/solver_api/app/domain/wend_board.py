from __future__ import annotations

from .errors import InvalidBoard
from .models import JsonDict


def validate_wend_board(payload: object) -> JsonDict:
    """Validate visible page data before it can bypass image recognition."""
    if not isinstance(payload, dict) or set(payload) != {"board", "lengths"}:
        raise InvalidBoard("Wend page data must contain board and lengths.")
    board, lengths = payload["board"], payload["lengths"]
    if not isinstance(board, list) or not 5 <= len(board) <= 8:
        raise InvalidBoard("Wend page data must have a square board of size 5 through 8.")
    visible = 0
    for row in board:
        if not isinstance(row, list) or len(row) != len(board):
            raise InvalidBoard("Wend page data must have a square board.")
        for letter in row:
            if letter is None:
                continue
            if not isinstance(letter, str) or len(letter) != 1 or not "A" <= letter <= "Z":
                raise InvalidBoard("Wend page cells must be uppercase ASCII letters or null holes.")
            visible += 1
    if (not isinstance(lengths, list) or not lengths or len(lengths) > 21
            or any(type(length) is not int or not 3 <= length <= 16 for length in lengths)
            or sum(lengths) != visible):
        raise InvalidBoard("Wend answer lengths must cover every visible cell exactly once.")
    return {"board": [list(row) for row in board], "lengths": sorted(lengths)}
