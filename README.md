# LinkedIn Puzzle Solvers

Monorepo for computer vision solvers for LinkedIn daily puzzles.

## Projects

- `games/queen_solver`: solver for the Queens puzzle.
- `games/tango_solver`: solver for the Tango puzzle.
- `services/solver_api`: local FastAPI service that exposes both solvers.
- `extension`: Chrome extension scaffold for board selection, capture, solving, and overlays.

The `games/*` projects were imported from their original repositories with history preserved.

## Highlights

- Unified local API for Queens and Tango solvers.
- Chrome extension with board select, auto-detect, solve, and apply.
- One-click `Solve + Apply` flow in extension popup.
- Configurable apply settings (auto-close, click delays, Tango input mode).

## Quick Start

1. Create and activate a Python virtual environment at repo root.
2. Install API dependencies:

```bash
pip install -r services/solver_api/requirements.txt
```

3. Run the local API:

```bash
cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Load the extension in Chrome from `extension/` via `chrome://extensions`.

## API Endpoints

- `GET /health`
- `POST /solve/queens` (multipart form field: `image`)
- `POST /solve/tango` (multipart form field: `image`)

## CI and Release

- CI workflow: `.github/workflows/ci.yml`
- Smoke checks: `scripts/smoke_check.py`
- Release guide: `docs/release.md`

See `services/solver_api/README.md` and `extension/README.md` for details.
