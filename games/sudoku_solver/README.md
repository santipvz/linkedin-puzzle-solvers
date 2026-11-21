# Mini Sudoku Solver

Computer vision and backtracking solver for LinkedIn Mini Sudoku.

## Input from the page

Mini Sudoku is a separate, non-React app inside the `/games/view/mini-sudoku/desktop` iframe. Its cells carry readable classes, so the extension reads the preset digits straight from them: `.sudoku-cell-prefilled` and `.sudoku-cell-content`. Digits the player typed are not clues and are left out. The extension sends `{"board": [[0, 1, 0, 0, 0, 0], ...]}` as `parsed_board`, with 0 for blank cells. The worker only applies a solution when it is unique.

The OCR pipeline below is only used when the page can't be read. `tests/fixtures/linkedin-2026-11-20.json` records a real page board.

## Puzzle Rules

- Grid size is `6x6`.
- Digits are `1..6`.
- Every row contains each digit once.
- Every column contains each digit once.
- Sub-grids are `2x3` (2 rows tall by 3 columns wide).

## Run

From repo root:

```bash
python3 -m pip install -r requirements.txt
python3 games/sudoku_solver/main.py games/sudoku_solver/examples/sample1.png
```

Print full JSON payload:

```bash
python3 games/sudoku_solver/main.py games/sudoku_solver/examples/sample1.png --json
```

## Notes

- OCR training reuses glyph masks from local sans-serif fonts. The training dataset is cached on disk by font fingerprint, and the model is cached for the process lifetime.
- Input images can be full screenshots or already-cropped board captures.

The extension captures the outer `.sudoku-board` frame with an 8 CSS-pixel margin so all seven grid lines survive fractional display scaling. Applying numbers continues to locate the inner `.sudoku-grid` cells. The November 2 fixture contains only the public daily board and its frame, without account or page content.
