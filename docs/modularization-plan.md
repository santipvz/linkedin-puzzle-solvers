# Modularization Plan

This document defines an incremental path to simplify solver code and avoid repeated logic.

## Target Structure

- `core/vision/`
  - projection and line grouping helpers
  - board bbox candidate scoring helpers
  - shared morphology/threshold presets
- `core/commons/`
  - deterministic board + grid detector used by all games
  - crop and grid-bound utilities shared by parsers/workers
- `core/ocr/`
  - reusable OCR preprocessing helpers
  - confidence ranking utilities
- `core/runtime/`
  - runtime path/bootstrap helpers for solver-local execution
- `core/types/`
  - shared typed payloads for parser metadata

## Completed in Phase 1

- Added `core/vision/line_projection.py`.
- Removed duplicate line-group/subset/span logic from:
  - `games/tango_solver/src/grid_detector.py`
  - `games/tango_solver/src/image_parser.py`
  - `games/sudoku_solver/src/image_parser.py`
  - `games/patches_solver/src/image_parser.py`

## Completed in Phase 2 (Incremental)

- Added `core/vision/parsed_board_payload.py` for shared parser metadata payload construction.
- Adopted shared parser payload helper in:
  - `games/sudoku_solver/src/image_parser.py`
  - `games/zip_solver/src/image_parser.py`
  - `games/patches_solver/src/image_parser.py`
  - `games/tango_solver/src/image_parser.py`
- Expanded worker shared helpers in `services/solver_api/app/workers/common.py`:
  - board-size normalization/inference (`parsed_board_size`)
  - generic grid normalization (`normalize_int_grid`)
  - bbox derivation from `grid_coords` (`board_bbox_from_grid_coords`)
- Replaced duplicated worker-local helper implementations in Sudoku, Tango, and Queens workers.

## Completed in Phase 3 (Deterministic Board Detection)

- Added `core/commons/board_detection.py` with shared deterministic board/grid detection.
- Adopted shared detector in Sudoku, Tango, Zip, and Patches parsers.
- Adopted shared detector in Queens board detector and Queens worker crop flow.

## Phase 2 Candidates

- Extract reusable board bbox scoring into `core/vision/board_bbox.py`.
- Extract grid line builders into `core/vision/grid_lines.py`.
- Normalize parser metadata payload types across games.
- Add shared parser smoke runner script for all games.

## Safe Refactor Rules

1. Keep puzzle-specific heuristics in each solver; move only puzzle-agnostic logic to common.
2. Require one smoke check per touched solver after each extraction.
3. Keep dataset benchmark gates green where available.
4. Refactor in small vertical slices to avoid cross-solver regressions.

## Architecture Reference

- End-to-end architecture and runtime flow diagram: `docs/architecture.md`
