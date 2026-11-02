# Mini Sudoku Solver

Computer vision and backtracking solver for LinkedIn Mini Sudoku.

## Puzzle Rules

- Grid size is `6x6`.
- Digits are `1..6`.
- Every row contains each digit once.
- Every column contains each digit once.
- Sub-grids are `2x3` (2 rows tall by 3 columns wide).

## Run

From repo root:

```bash
python3 -m pip install -r games/sudoku_solver/requirements.txt
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
