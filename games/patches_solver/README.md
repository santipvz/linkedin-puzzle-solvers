# Patches Solver

Computer vision parser + rectangle tiling solver for LinkedIn Patches.

## Input from the page

The extension reads the puzzle that LinkedIn's game already holds in memory (see `extension/page_puzzle.js`), so normal solves need no OCR. It sends this as `parsed_board`:

```json
{"size": 7, "clues": [[1, "square", null], [5, "any", 3], [11, "wide", null]]}
```

Each clue is `[cell, shape, area]`:
- `cell` is `row * size + col`.
- `shape` is `any`, `square`, `wide` or `tall`.
- `area` is null when the clue shows no number.

With page data, the worker never relaxes square clues, since that fallback only exists for shapes OCR misread. Non-square boards keep using the image, because the solver handles square boards only. `tests/fixtures/linkedin-2026-11-20.json` records a real page board, and our answer for it matches LinkedIn's.

## Rules modeled

- The board is tiled with non-overlapping axis-aligned rectangles.
- Every clue belongs to exactly one rectangle.
- If a clue has a number, the rectangle area must match it.
- Shape constraints:
  - `square`: width == height
  - `wide`: width > height
  - `tall`: height > width
  - `any`: no aspect restriction

## Local run

```bash
python3 games/patches_solver/main.py games/patches_solver/examples/sample1.png --json
```

Available board captures:

- `games/patches_solver/examples/sample1.png`
- `games/patches_solver/examples/sample2.png`
- `games/patches_solver/examples/sample3.png`
- `games/patches_solver/examples/sample4.png`: 8x8 board with 14 clues and only four numbered clues.

Boards with fewer numbered clues than the usual OCR threshold are accepted only when a capped search proves that the original clues have exactly one tiling, without relaxing shapes or changing OCR values. Multiple or unproven solutions remain blocked.

## Tests

```bash
python3 -m unittest discover -s games/patches_solver/tests -p "test_*.py"
```
