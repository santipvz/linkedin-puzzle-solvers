# Zip Solver

Computer vision and path-search solver for LinkedIn Zip.

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
