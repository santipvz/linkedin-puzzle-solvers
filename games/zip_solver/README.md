# Zip Solver

Path-search solver for LinkedIn Zip.

## Checking OCR against the page

The board is always solved from the screenshot. When the extension can also read the puzzle the game holds in memory (see `extension/page_puzzle.js`), it sends it as `parsed_board`, and the worker reports in `details.ocr_check` whether OCR read the board correctly: `matches`, `mismatch_count` and up to 12 `mismatches` such as `{"at": "r1c5 clue", "page": 1, "ocr": 7}`. That page board never changes the answer, and an invalid one is ignored with a reason.

Zip's page board:

```json
{"size": 7, "sequence": [12, 11, 9, 17, 24, 36, 37, 31, 39, 8, 40], "walls": [[1, "down"], [3, "down"]]}
```

- Cells are numbered `row * size + col`.
- `sequence` lists the numbered cells in order, so `sequence[0]` holds 1.
- `walls` lists `[cell, direction]` pairs, with direction `up`, `down`, `left` or `right`.
- The check compares numbered cells and walls.

Some boards hide numbers behind a "?" ("mystery" cells), which OCR can't read; the page board still knows their order. `tests/fixtures/linkedin-2026-11-20.json` records a real page board.

## Puzzle Rules

- Draw one continuous path.
- Path starts at clue `1` and reaches clues in ascending order.
- Black walls block movement between neighboring cells.
- Every board cell must be visited exactly once.

## Run

From repo root:

```bash
python3 -m pip install -r requirements.txt
python3 games/zip_solver/main.py games/zip_solver/examples/sample1.png
```

Print full JSON payload:

```bash
python3 games/zip_solver/main.py games/zip_solver/examples/sample1.png --json
```
