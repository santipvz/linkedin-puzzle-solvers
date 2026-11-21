# Mini Sudoku Solver

Computer vision and backtracking solver for LinkedIn Mini Sudoku.

## Checking OCR against the page

The board is always solved from the screenshot. When the extension can also read the puzzle the game holds in memory (see `extension/page_puzzle.js`), it sends it as `parsed_board`, and the worker reports in `details.ocr_check` whether OCR read the board correctly: `matches`, `mismatch_count` and up to 12 `mismatches` such as `{"at": "r1c5 clue", "page": 1, "ocr": 7}`. That page board never changes the answer, and an invalid one is ignored with a reason.

Mini Sudoku is a separate, non-React app inside the `/games/view/mini-sudoku/desktop` iframe, so the extension reads its preset digits from the cells' classes (`.sudoku-cell-prefilled`, `.sudoku-cell-content`); digits the player typed are not clues. The page board is `{"board": [[0, 1, 0, 0, 0, 0], ...]}` with 0 for blanks. The check compares it with the preset digits the solve actually used, after OCR and its conflict recovery.

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
