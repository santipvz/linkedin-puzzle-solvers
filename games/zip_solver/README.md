# Zip Solver

Path-search solver for LinkedIn Zip.

## Input

The extension reads the puzzle that LinkedIn's game already holds in memory (see `extension/page_puzzle.js`), so normal solves need no OCR. It sends this as `parsed_board`:

```json
{"size": 7, "sequence": [12, 11, 9, 17, 24, 36, 37, 31, 39, 8, 40], "walls": [[1, "down"], [3, "down"]]}
```

- Cells are numbered `row * size + col`.
- `sequence` lists the numbered cells in order, so `sequence[0]` holds 1.
- `walls` lists `[cell, direction]` pairs, with direction `up`, `down`, `left` or `right`.

Some boards hide numbers behind a "?" ("mystery" cells). The page data still gives their order, so they solve like any other board.

When the page puzzle can't be read, the worker falls back to the image parser described below. `tests/fixtures/linkedin-2026-11-20.json` records a real page board. Our solver's path for it matches LinkedIn's own answer.

## Puzzle Rules

- Draw one continuous path.
- Path starts at clue `1` and reaches clues in ascending order.
- Black walls block movement between neighboring cells.
- Every board cell must be visited exactly once.

## Run

From repo root:

```bash
python3 -m pip install -r games/zip_solver/requirements.txt
python3 games/zip_solver/main.py games/zip_solver/examples/sample1.png
```

Print full JSON payload:

```bash
python3 games/zip_solver/main.py games/zip_solver/examples/sample1.png --json
```
