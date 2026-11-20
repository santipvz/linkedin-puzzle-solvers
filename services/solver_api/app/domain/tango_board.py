from __future__ import annotations

from .errors import InvalidBoard
from .models import JsonDict


TANGO_SIZE = 6
KEYS = ("size", "suns", "moons", "equal", "opposite")
# The Tango solver encodes pieces as 0 = moon and 1 = sun.
MOON, SUN = 0, 1


def validate_tango_board(payload: object) -> JsonDict:
    """Validate a Tango puzzle read from the page.

    Cells are numbered ``row * size + col``. ``suns`` and ``moons`` list the
    preset cells, and ``equal`` / ``opposite`` list the ``=`` and ``x`` clues
    between two orthogonally adjacent cells.
    """
    if not isinstance(payload, dict) or set(payload) != set(KEYS):
        raise InvalidBoard("Tango page data must contain only size, suns, moons, equal and opposite.")
    size = payload["size"]
    if type(size) is not int or size != TANGO_SIZE:
        raise InvalidBoard(f"Tango boards must be {TANGO_SIZE}x{TANGO_SIZE}.")
    cells = size * size

    def is_cell(value: object) -> bool:
        return type(value) is int and 0 <= value < cells

    presets: list[int] = []
    for key in ("suns", "moons"):
        values = payload[key]
        if not isinstance(values, list) or not all(is_cell(cell) for cell in values):
            raise InvalidBoard(f"Tango {key} must list cells on the board.")
        presets += values
    if len(set(presets)) != len(presets):
        raise InvalidBoard("A Tango cell cannot hold two preset pieces.")
    for key in ("equal", "opposite"):
        clues = payload[key]
        if not isinstance(clues, list) or len(clues) > 2 * cells:
            raise InvalidBoard(f"Tango {key} clues must be a list.")
        for clue in clues:
            if not isinstance(clue, list) or len(clue) != 2 or not all(is_cell(cell) for cell in clue):
                raise InvalidBoard(f"Tango {key} clues must be [cell, cell] pairs.")
            (r1, c1), (r2, c2) = divmod(clue[0], size), divmod(clue[1], size)
            if abs(r1 - r2) + abs(c1 - c2) != 1:
                raise InvalidBoard(f"Tango {key} clues must join adjacent cells.")
    return {key: payload[key] if key == "size" else [list(item) if isinstance(item, list) else item for item in payload[key]] for key in KEYS}


def tango_solver_input(board: JsonDict) -> tuple[list[tuple[int, int, int]], list[tuple[str, tuple[int, int], tuple[int, int]]]]:
    """Fixed pieces as (row, col, piece) and clues as (type, pos1, pos2) for TangoSolver."""
    size = board["size"]
    fixed = [(*divmod(cell, size), SUN) for cell in board["suns"]] + [(*divmod(cell, size), MOON) for cell in board["moons"]]
    constraints = [
        (symbol, divmod(a, size), divmod(b, size))
        for key, symbol in (("equal", "="), ("opposite", "x"))
        for a, b in board[key]
    ]
    return fixed, constraints
