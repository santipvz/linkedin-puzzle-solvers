from __future__ import annotations

from .errors import InvalidBoard
from .ocr_check import cell_name
from .models import JsonDict


MIN_SIZE = 4
MAX_SIZE = 10
SHAPES = {"any", "square", "wide", "tall"}


def validate_patches_board(payload: object) -> JsonDict:
    """Validate a Patches puzzle read from the page.

    ``clues`` lists ``[cell, shape, area]``: the clue's cell (``row * size + col``),
    the rectangle shape it asks for (``any``, ``square``, ``wide`` or ``tall``) and
    its area, or null when the clue shows no number.
    """
    if not isinstance(payload, dict) or set(payload) != {"size", "clues"}:
        raise InvalidBoard("Patches page data must contain only size and clues.")
    size, clues = payload["size"], payload["clues"]
    if type(size) is not int or not MIN_SIZE <= size <= MAX_SIZE:
        raise InvalidBoard(f"Patches boards must be {MIN_SIZE} through {MAX_SIZE} cells wide.")
    cells = size * size
    if not isinstance(clues, list) or not clues or len(clues) > cells:
        raise InvalidBoard("Patches page data must list its clues.")
    seen: set[int] = set()
    for clue in clues:
        if (not isinstance(clue, list) or len(clue) != 3 or type(clue[0]) is not int or not 0 <= clue[0] < cells
                or clue[1] not in SHAPES
                or not (clue[2] is None or (type(clue[2]) is int and 1 <= clue[2] <= cells))):
            raise InvalidBoard('Patches clues must be [cell, "any" | "square" | "wide" | "tall", area or null].')
        if clue[0] in seen:
            raise InvalidBoard("Two Patches clues share a cell.")
        seen.add(clue[0])
    return {"size": size, "clues": [list(clue) for clue in clues]}


def patches_solver_clues(board: JsonDict) -> list[JsonDict]:
    """Clues in the PatchesSolver input format."""
    size = board["size"]
    return [
        {"row": cell // size, "col": cell % size, "shape": shape, "area": area}
        for cell, shape, area in board["clues"]
    ]


def patches_board_facts(clues: list[JsonDict]) -> dict[str, object]:
    """Each clue's shape and area, from either the page board or the OCR parse."""
    return {
        f"{cell_name(int(clue['row']), int(clue['col']))} clue": f"{clue.get('shape') or 'any'} {clue.get('area') or '-'}"
        for clue in clues
    }


def patches_page_facts(board: JsonDict) -> dict[str, object]:
    return patches_board_facts(patches_solver_clues(board))
