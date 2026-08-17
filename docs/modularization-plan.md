# Modularization Status

This document records the implemented boundary between shared computer-vision mechanics and puzzle-specific policy.

## Shared Core

- `core/commons/board_detection.py`
  - validated image-relative bounding boxes
  - safe clipping and cropping
  - uniform crop-local grid boundaries
  - external contour measurements without game-specific selection
  - horizontal and vertical morphology projections
- `core/vision/line_projection.py`
  - contiguous projection groups
  - regular line subset selection
- `core/vision/ocr.py`
  - normalized cosine template matching with batch prediction
  - distance-weighted KNN
  - common OCR prediction types
- `core/vision/parsed_board_payload.py`
  - validated board metadata serialization

These APIs are covered once under `tests/core/` instead of repeating geometry and OCR-math tests for every game.

## Puzzle Policy

Each game continues to own:

- masks, color spaces, thresholds, and morphology parameters
- contour acceptance and candidate scoring
- board-size selection and fallback behavior
- glyph segmentation and confidence policy
- clue interpretation and solver rules

A universal detector is intentionally avoided because the games use different evidence. Queens relies on regions, Patches on dashed separators, Zip on clue continuity, and Wend on answer lengths and blocked cells.

## Current Adoption

- Tango and Sudoku share projection grouping and regular-line selection.
- Sudoku and Patches share distance-weighted KNN.
- Patches, Sudoku, Zip, and Wend share contour measurement and safe cropping.
- Tango, Zip, Patches, and Wend emit common parser metadata.
- Wend uses shared uniform geometry and batch cosine OCR.

## Next Candidates

- Migrate Sudoku crop metadata after fixture parity is established.
- Replace generic `src` package names with unique installable packages.
- Remove the global worker import lock after package isolation.
- Extract pure extension geometry into testable modules.

## Safe Refactor Rules

1. Share mechanics, not puzzle policy.
2. Add generic core tests before migrating a parser.
3. Keep one representative end-to-end fixture per game.
4. Run `python3 scripts/quality_check.py` after each vertical slice.
