# LinkedIn Puzzle Solvers

Monorepo for computer vision solvers and browser automation for LinkedIn daily puzzles.

## Repository Layout

- `games/queen_solver`: Queens solver.
- `games/tango_solver`: Tango solver.
- `games/sudoku_solver`: Mini Sudoku solver.
- `games/zip_solver`: Zip solver.
- `games/patches_solver`: Patches solver.
- `services/solver_api`: FastAPI service exposing all puzzle solvers.
- `extension`: browser extension (board detection, solve, overlay, and apply).
- `deploy/local`: Docker deployment for running the API as a persistent local service.

## What You Get

- One API for all supported puzzles.
- Popup workflow: select board, solve, preview overlay, apply.
- In-page quick widget: one-click solve/apply on LinkedIn game pages.
- Dataset capture support for start-board screenshots.
- Configurable apply timings and behavior.

## Prerequisites

- Python 3.10+ (3.11 recommended).
- `pip`.
- Chrome or Firefox for the extension.
- Docker Desktop or Docker Engine + Compose plugin (only for Docker mode).

## Run the Solver API (Two Supported Modes)

Choose **one** of these modes.

### Mode A: Local Python Process (`uvicorn`)

Best for development and debugging.

1. Create and activate a virtual environment at repository root.
2. Install API dependencies.
3. Start the API with autoreload.
4. Verify health endpoint.

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/solver_api/requirements.txt

cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Use this API URL in the extension:

`http://127.0.0.1:8000`

### Mode B: Local Docker Service (`docker compose`)

Best for a stable background service that survives reboots.

1. Open the Docker deploy directory.
2. Create your environment file from template.
3. Start the service.
4. Verify container and health endpoint.

```bash
# from repo root
cd deploy/local
cp .env.example .env
mkdir -p ../../datasets
docker compose up -d --build
```

Check status:

```bash
cd deploy/local
docker compose ps
docker compose logs -f solver-api
curl http://127.0.0.1:18000/health
```

Use this API URL in the extension:

`http://127.0.0.1:18000`

You can customize port and capture paths in `deploy/local/.env`.

## Load and Use the Extension

1. Open browser extension page:
   - Chrome: `chrome://extensions`
   - Firefox: `about:debugging#/runtime/this-firefox`
2. Enable developer mode.
3. Load the extension from `extension/`.
4. Open a LinkedIn puzzle page.
5. In popup settings, set API URL:
   - `http://127.0.0.1:8000` for Uvicorn mode.
   - `http://127.0.0.1:18000` for Docker mode.
6. Use `Solve`, `Apply`, or `Solve + Apply`.

Supported game URLs:

- `https://www.linkedin.com/games/queens/`
- `https://www.linkedin.com/games/tango/`
- `https://www.linkedin.com/games/mini-sudoku/`
- `https://www.linkedin.com/games/zip/`
- `https://www.linkedin.com/games/patches/`

## API Endpoints

- `GET /health`
- `POST /solve/queens` (multipart field `image`)
- `POST /solve/tango` (multipart field `image`)
- `POST /solve/sudoku` (multipart field `image`)
- `POST /solve/zip` (multipart field `image`)
- `POST /solve/patches` (multipart field `image`)

## Common Maintenance Commands

Restart Uvicorn mode:

```bash
pkill -f "uvicorn app.main:app"
cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Restart Docker mode:

```bash
cd deploy/local
docker compose restart solver-api
```

Rebuild Docker service after pulling changes:

```bash
cd deploy/local
docker compose up -d --build
```

## CI and Release

- CI workflow: `.github/workflows/ci.yml`
- Smoke checks: `scripts/smoke_check.py`
- Release guide: `docs/release.md`

## Contributing and License

- Contribution guide: `CONTRIBUTING.md`
- License: `LICENSE` (MIT)

For more details, see `services/solver_api/README.md`, `extension/README.md`, and `deploy/local/README.md`.
