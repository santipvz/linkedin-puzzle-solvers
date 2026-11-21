from __future__ import annotations

from .errors import InvalidBoard
from .ocr_check import cell_name
from .models import JsonDict


MIN_SIZE = 4
MAX_SIZE = 12


def validate_queens_board(payload: object) -> JsonDict:
    """Validate a Queens puzzle read from the page.

    ``regions[row][col]`` is the colour region id of each cell. A board of
    size N has exactly N regions, each holding one queen.
    """
    if not isinstance(payload, dict) or set(payload) != {"size", "regions"}:
        raise InvalidBoard("Queens page data must contain only size and regions.")
    size, regions = payload["size"], payload["regions"]
    if type(size) is not int or not MIN_SIZE <= size <= MAX_SIZE:
        raise InvalidBoard(f"Queens boards must be {MIN_SIZE} through {MAX_SIZE} cells wide.")
    if (not isinstance(regions, list) or len(regions) != size
            or any(not isinstance(row, list) or len(row) != size for row in regions)):
        raise InvalidBoard("Queens regions must be a square grid matching size.")
    if any(type(region) is not int or not 0 <= region < 64 for row in regions for region in row):
        raise InvalidBoard("Queens region ids must be small non-negative integers.")
    if len({region for row in regions for region in row}) != size:
        raise InvalidBoard("A Queens board needs exactly one region per row.")
    return {"size": size, "regions": [list(row) for row in regions]}


def queens_board_facts(regions: list[list[int]]) -> dict[str, object]:
    """Which region each cell belongs to.

    Region ids are arbitrary (the page uses colour ids, OCR numbers regions as
    it finds them), so regions are renumbered in reading order: two boards
    match when they split the cells the same way.
    """
    renumbered: dict[int, int] = {}
    return {
        f"{cell_name(row, col)} region": renumbered.setdefault(region, len(renumbered))
        for row, values in enumerate(regions)
        for col, region in enumerate(values)
    }


def queens_page_facts(board: JsonDict) -> dict[str, object]:
    return queens_board_facts(board["regions"])
