# Wend Solver

Wend combines computer vision, letter OCR, dictionary-constrained path generation, and an exact-cover search.

## Rules

- Words follow orthogonally adjacent cells without reusing a cell.
- Every visible board cell belongs to exactly one answer.
- The answer slots below the board define the required word lengths.
- Board sizes from 5x5 through 8x8 are supported.

## Pipeline

1. Detect and safely crop the board using shared core geometry.
2. Read answer lengths from the slot rows below the board.
3. Select the board size using visible-cell count and grid alignment.
4. Classify letters with shared batch cosine OCR.
5. Generate dictionary paths through a trie.
6. Select a disjoint exact cover matching all answer lengths.

The parser owns Wend-specific thresholds, blocked-cell detection, answer-slot parsing, and size scoring. Shared core code owns only geometry and OCR math.

## Reliability

The worker auto-applies only when the board structure is consistent and the solution is uniquely enumerated. Responses expose OCR corrections, retained solution costs, exact-count status, and pipeline revision under `details`.

Capture the board and the answer slots below it. The extension automatically expands a board selection downward for this purpose.

## Dictionary

The portable dictionary is `data/words.txt`. Host dictionaries and hard-coded fallback answers are not used. See `data/README.md` and `data/SCOWL-NOTICE.txt` for provenance.

## Validation

```bash
python3 -m pytest games/wend_solver/tests tests/core
python3 services/solver_api/app/workers/solve_wend_worker.py games/wend_solver/examples/sample1.png
python3 scripts/wend_dataset_benchmark.py
```

The dataset benchmark is optional and uses ignored local captures. The tracked example is the reproducible CI smoke fixture.
