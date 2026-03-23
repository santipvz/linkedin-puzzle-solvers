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

- OCR is trained on startup from local sans-serif fonts and then cached for the process lifetime.
- Input images can be full screenshots or already-cropped board captures.
