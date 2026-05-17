# Architecture Overview

This document describes the current end-to-end architecture after the modularization and decoupling passes.

## Design Goals

- Keep puzzle-specific heuristics inside each solver package.
- Move puzzle-agnostic logic to shared modules.
- Keep API contracts stable while refactoring internals.
- Validate every refactor with compile, tests, smoke checks, and dataset benchmarks.

## Layered Architecture

- Client layer:
  - Browser extension (`extension/`) captures board screenshots, calls API, previews moves, applies moves.
- API layer:
  - FastAPI service (`services/solver_api/app`) routes `/solve/<puzzle>` requests.
- Worker orchestration layer:
  - Per-puzzle workers in `services/solver_api/app/workers` orchestrate parse -> solve -> response.
  - Shared worker helpers in `services/solver_api/app/workers/common.py` provide runtime bootstrap and normalized utilities.
- Solver packages:
  - `games/*_solver/src/image_parser.py` parses board state from image.
  - `games/*_solver/src/*solver*.py` computes solution/moves.
- Shared core modules:
  - `core/commons/board_detection.py` for deterministic board and grid detection.
  - `core/vision/line_projection.py` for projection/line grouping helpers.
  - `core/vision/parsed_board_payload.py` for common parser metadata payload construction.
- Data and operations:
  - `datasets/` stores captured datasets.
  - `scripts/` runs smoke checks and benchmarks.
  - `docs/` stores release and architecture documentation.

## End-to-End Flow

1. Extension captures the active puzzle board image.
2. Extension sends image to the solver API endpoint for the detected puzzle type.
3. API dispatches to the corresponding worker.
4. Worker activates the puzzle import context and calls the puzzle parser.
5. Parser uses shared core vision helpers where applicable and emits normalized metadata.
6. Worker calls the puzzle solver and shapes a stable API response.
7. Extension receives moves/solution grid and applies them in the page UI.

## Architecture Diagram

```mermaid
flowchart LR
    U[User] --> E[Browser Extension\nextension/]

    subgraph API[Solver API\nservices/solver_api]
        R[FastAPI Routes\n/solve/*]
        W0[Worker Common\nworkers/common.py]
        W1[Queens Worker]
        W2[Tango Worker]
        W3[Sudoku Worker]
        W4[Zip Worker]
        W5[Patches Worker]
    end

    subgraph CORE[Shared Core\ncore/*]
        C0[commons/board_detection.py]
        C1[line_projection.py]
        C2[parsed_board_payload.py]
    end

    subgraph GAMES[Puzzle Packages\ngames/*_solver/src]
        P1[image_parser.py]
        S1[solver.py / queens_solver.py / ...]
    end

    subgraph OPS[Data + Tooling]
        D1[datasets/]
        D2[scripts/smoke_check.py\nscripts/tango_dataset_benchmark.py]
        D3[docs/]
    end

    E -->|POST image| R
    R --> W1
    R --> W2
    R --> W3
    R --> W4
    R --> W5

    W1 --> W0
    W2 --> W0
    W3 --> W0
    W4 --> W0
    W5 --> W0

    W1 --> P1
    W2 --> P1
    W3 --> P1
    W4 --> P1
    W5 --> P1

    P1 --> C1
    P1 --> C2
    P1 --> C0
    P1 --> S1
    S1 --> W1
    S1 --> W2
    S1 --> W3
    S1 --> W4
    S1 --> W5

    W1 -->|JSON solution| E
    W2 -->|JSON solution| E
    W3 -->|JSON solution| E
    W4 -->|JSON solution| E
    W5 -->|JSON solution| E

    E -. capture/benchmark inputs .-> D1
    D2 --> API
    D3 --> API
    D3 --> CORE
    D3 --> GAMES
```

## Current Decoupling Status

- Shared parser metadata payload builder is used by Sudoku, Zip, Patches, and Tango parsers.
- Worker-side shared helpers centralize board-size inference and grid normalization.
- Puzzle-specific OCR and solving logic remains isolated per game package.
