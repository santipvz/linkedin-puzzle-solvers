# Patches Solver

Computer vision parser + rectangle tiling solver for LinkedIn Patches.

## Checking OCR against the page

The board is always solved from the screenshot. When the extension can also read the puzzle the game holds in memory (see `extension/page_puzzle.js`), it sends it as `parsed_board`, and the worker reports in `details.ocr_check` whether OCR read the board correctly: `matches`, `mismatch_count` and up to 12 `mismatches` such as `{"at": "r1c5 clue", "page": 1, "ocr": 7}`. That page board never changes the answer, and an invalid one is ignored with a reason.

Patches' page board is `{"size": 7, "clues": [[1, "square", null], [5, "any", 3]]}`. Each clue is `[cell, shape, area]`:
- `cell` is `row * size + col`.
- `shape` is `any`, `square`, `wide` or `tall`.
- `area` is null when the clue shows no number.

The check compares each clue's shape and number.

## Rules modeled

- The board is tiled with non-overlapping axis-aligned rectangles.
- Every clue belongs to exactly one rectangle.
- If a clue has a number, the rectangle area must match it.
- Shape constraints:
  - `square`: width == height
  - `wide`: width > height
  - `tall`: height > width
  - `any`: no aspect restriction
- No region is a single cell. LinkedIn's own rectangle enumerator skips 1x1, so neither does the solver.

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
