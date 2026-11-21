"""Compare what OCR read from a screenshot with the board the game itself holds.

The extension reads the puzzle from the game page and sends it next to the
screenshot. The board is still solved from the image; the page board only
says whether OCR read it correctly. Each game describes its board as a set of
facts ("r1c2 clue": 4, "r0c3|r1c3 wall": True, ...) so one comparison works
for all of them.
"""

from __future__ import annotations

from collections.abc import Mapping

from .models import JsonDict


MAX_REPORTED_MISMATCHES = 12
Facts = Mapping[str, object]


def cell_name(row: int, col: int) -> str:
    return f"r{row}c{col}"


def compare_board_facts(page: Facts, ocr: Facts) -> JsonDict:
    """Report every fact the screenshot reading got wrong, missed or invented."""
    mismatches = [
        {"at": key, "page": page.get(key), "ocr": ocr.get(key)}
        for key in sorted(set(page) | set(ocr))
        if page.get(key) != ocr.get(key)
    ]
    return {
        "matches": not mismatches,
        "checked": len(page),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:MAX_REPORTED_MISMATCHES],
    }


def check_ocr(validate, page_board: object, page_facts, ocr_facts: Facts) -> JsonDict:
    """Validate the page board, then compare it with the OCR facts.

    A page board that can't be validated never affects the OCR solve; the
    check just says why it was skipped.
    """
    try:
        board = validate(page_board)
    except Exception as exc:  # InvalidBoard, or a malformed payload
        return {"matches": None, "error": f"Page board ignored: {exc}"}
    return compare_board_facts(page_facts(board), ocr_facts)
