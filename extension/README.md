# Browser Extension

Browser extension for solving LinkedIn daily puzzles through the local solver API.

## Features

- Manual board selection on the active tab.
- Auto board detection (top page + iframe-aware).
- Solve via API endpoints for Queens, Tango, Mini Sudoku, Zip, and Patches.
- Overlay preview for detected moves.
- Auto-apply support:
  - Queens: click-based input.
  - Tango: configurable click strategy.
  - Mini Sudoku: strict cell-target + keyboard input.
  - Zip: start click + arrow keys.
  - Patches: rectangle drag from corner to corner.
- Popup actions: `Select Board`, `Auto Detect`, `Solve`, `Apply`, `Solve + Apply`.
- In-page quick solve widget (`Solve <Game>`).

## Step 1: Start the Solver API (Choose One)

The extension needs a running API backend.

### Option A: Uvicorn (port 8000)

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/solver_api/requirements.txt

cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API URL to configure in extension:

`http://127.0.0.1:8000`

### Option B: Docker Compose (port 18000)

```bash
# from repo root
cd deploy/local
cp .env.example .env
mkdir -p ../../datasets
docker compose up -d --build
```

API URL to configure in extension:

`http://127.0.0.1:18000`

## Step 2: Load Extension in Browser

### Chrome / Chromium

1. Open `chrome://extensions`.
2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Select the `extension/` folder.

### Firefox (temporary install)

1. Open `about:debugging#/runtime/this-firefox`.
2. Click `Load Temporary Add-on`.
3. Select `extension/manifest.json`.

Notes:

- Temporary Firefox add-ons are removed on browser restart.
- For persistent Firefox distribution, package/sign the extension separately.

## Step 3: Configure and Use

1. Open one of these pages:
   - `https://www.linkedin.com/games/queens/`
   - `https://www.linkedin.com/games/tango/`
   - `https://www.linkedin.com/games/mini-sudoku/`
   - `https://www.linkedin.com/games/zip/`
   - `https://www.linkedin.com/games/patches/`
2. Click the extension icon.
3. Set the API URL (`8000` for Uvicorn or `18000` for Docker).
4. Select puzzle type (or let quick widget auto-detect).
5. Use either flow:
   - Popup: `Select Board` / `Auto Detect` -> `Solve` -> `Apply`.
   - Popup shortcut: `Solve + Apply`.
   - In-page widget: click `Solve <Game>`.

## Troubleshooting

- If solve fails, check API health:

```bash
curl http://127.0.0.1:8000/health
# or Docker mode:
curl http://127.0.0.1:18000/health
```

- If quick widget does not appear, refresh the LinkedIn game page.
- If board detection misses once, run `Select Board` manually and reuse it.
- LinkedIn games run in an iframe; this extension includes frame-aware mapping for detection, overlay, and apply.
- If Firefox shows `background.service_worker is currently disabled. Add background.scripts.`, remove and reload the temporary add-on from `extension/manifest.json` after pulling latest changes.
