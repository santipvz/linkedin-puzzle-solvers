# Wend Solver

Wend combines computer vision, letter OCR, dictionary-constrained path generation, and an exact-cover search.

## Rules

- Words follow orthogonally adjacent cells without reusing a cell.
- Every visible board cell belongs to exactly one answer.
- The answer slots below the board define the required word lengths.
- Board sizes from 5x5 through 8x8 are supported.

## Pipeline

When the extension can read every indexed page cell, explicit hole marker and answer-slot row, it sends validated `parsed_board` data alongside the capture. The worker then searches the exact visible letters without initializing OCR. Invalid or incomplete page reads fall back to the image pipeline below. The page board must match the captured board's geometry, and the API checks size, alphabet, lengths and visible-cell totals before using it.

1. Detect and safely crop the board using shared core geometry.
2. Read answer lengths from the slot rows below the board.
3. Select the board size using visible-cell count and grid alignment.
4. Classify letters with shared batch cosine OCR.
5. Generate dictionary paths through a trie, trying the original letters first and OCR alternatives only if no exact cover exists.
6. Select a disjoint exact cover matching all answer lengths.

The parser owns Wend-specific thresholds, blocked-cell detection, answer-slot parsing, and size scoring. Shared core code owns only geometry and OCR math.

## Reliability

The worker auto-applies only when the board structure is consistent and the solution is uniquely enumerated. Responses expose `input_source` (`page` or `image`), diagnostic `candidate_word_sets`, OCR corrections, retained solution costs, exact-count status, and pipeline revision under `details`. Page input still rejects genuine dictionary/path ambiguity; it does not choose an arbitrary cover.

`tests/fixtures/linkedin-2026-10-29.json` records the public letters and lengths from Wend 143. Those letters have one cover: OAR, FLOOR, MIRROR, OREGANO and FOOTWORK.

The Docker image includes DejaVu, Liberation, and Noto Sans fonts for letter templates. Missing Noto templates can confuse letters such as R/P and introduce spurious alternatives. The template cache is keyed by the available font files and their metadata so font changes rebuild the OCR templates.

For direct Python runs on Debian/Ubuntu, install the same fonts with `sudo apt-get install fonts-dejavu-core fonts-liberation fonts-noto-core`.

`examples/sample2.png` is a 7x7 regression capture with 44 letters and six words, including an R that was misread as P in the earlier Docker image.

`examples/sample3.png` through `sample6.png` cover October 27, 21, 19, and 26: readable boards previously rejected because OCR alternatives introduced false ambiguity, and a board requiring the supplemental dictionary entry BIOME. Multiple covers of the original letters, or multiple covers during OCR recovery, are still rejected.

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
