from __future__ import annotations

from .errors import InvalidBoard
from .ocr_check import cell_name
from .models import JsonDict


MIN_SIZE = 3
MAX_SIZE = 10
WALL_DIRECTIONS = {"up", "down", "left", "right"}


def validate_zip_board(payload: object) -> JsonDict:
    """Validate a Zip puzzle read from the page.

    ``sequence`` lists the numbered cells in order (cell index = row * size + col),
    so ``sequence[0]`` holds 1. ``walls`` lists ``[cell, direction]`` pairs.
    """
    if not isinstance(payload, dict) or set(payload) != {"size", "sequence", "walls"}:
        raise InvalidBoard("Zip page data must contain only size, sequence and walls.")
    size, sequence, walls = payload["size"], payload["sequence"], payload["walls"]
    if type(size) is not int or not MIN_SIZE <= size <= MAX_SIZE:
        raise InvalidBoard(f"Zip boards must be {MIN_SIZE} through {MAX_SIZE} cells wide.")
    cells = size * size
    if (not isinstance(sequence, list) or len(sequence) < 2
            or any(type(cell) is not int or not 0 <= cell < cells for cell in sequence)
            or len(set(sequence)) != len(sequence)):
        raise InvalidBoard("Zip sequence must list at least two distinct cells on the board.")
    if not isinstance(walls, list) or len(walls) > 4 * cells:
        raise InvalidBoard("Zip walls must be a list.")
    for wall in walls:
        if (not isinstance(wall, list) or len(wall) != 2 or type(wall[0]) is not int
                or not 0 <= wall[0] < cells or wall[1] not in WALL_DIRECTIONS):
            raise InvalidBoard('Zip walls must be [cell, "up" | "down" | "left" | "right"] pairs.')
    return {"size": size, "sequence": list(sequence), "walls": [list(wall) for wall in walls]}


def zip_solver_input(board: JsonDict) -> tuple[list[list[bool]], list[list[bool]], dict[tuple[int, int], int]]:
    """Turn a validated page board into the solver's wall grids and numbered clues."""
    size = board["size"]
    blocked_h = [[False] * size for _ in range(size - 1)]  # between (r, c) and (r + 1, c)
    blocked_v = [[False] * (size - 1) for _ in range(size)]  # between (r, c) and (r, c + 1)
    for cell, direction in board["walls"]:
        row, col = divmod(cell, size)
        if direction == "up":
            row, direction = row - 1, "down"
        elif direction == "left":
            col, direction = col - 1, "right"
        if direction == "down" and 0 <= row < size - 1:
            blocked_h[row][col] = True
        elif direction == "right" and 0 <= col < size - 1:
            blocked_v[row][col] = True
    clues = {divmod(cell, size): number for number, cell in enumerate(board["sequence"], start=1)}
    return blocked_h, blocked_v, clues


def zip_board_facts(
    clues: dict[tuple[int, int], int], blocked_h: list[list[bool]], blocked_v: list[list[bool]],
) -> dict[str, object]:
    """Numbered cells and walls, from either the page board or the OCR parse."""
    facts: dict[str, object] = {f"{cell_name(row, col)} clue": int(value) for (row, col), value in clues.items()}
    for row, values in enumerate(blocked_h):
        facts.update({f"{cell_name(row, col)}|{cell_name(row + 1, col)} wall": True for col, wall in enumerate(values) if wall})
    for row, values in enumerate(blocked_v):
        facts.update({f"{cell_name(row, col)}|{cell_name(row, col + 1)} wall": True for col, wall in enumerate(values) if wall})
    return facts


def zip_page_facts(board: JsonDict) -> dict[str, object]:
    blocked_h, blocked_v, clues = zip_solver_input(board)
    return zip_board_facts(clues, blocked_h, blocked_v)
