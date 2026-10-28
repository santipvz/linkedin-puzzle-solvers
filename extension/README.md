# Browser Extension

Browser extension for solving LinkedIn daily puzzles through the online or local solver API.

Install from the stable `main` branch or a release tag. `develop` contains work for the next release. See the [release guide](../docs/release.md) for packaging and distribution.

## Features

- Manual board selection on the active tab.
- Auto board detection (top page + iframe-aware).
- Solve via API endpoints for Queens, Tango, Mini Sudoku, Zip, Patches, and Wend.
- Overlay preview for detected moves.
- Auto-apply support:
  - Queens: click-based input.
  - Tango: configurable click strategy.
  - Mini Sudoku: stable 36-cell grid detection and verified keyboard input; stops on unconfirmed writes.
  - Zip: start click + arrow keys.
  - Patches: rectangle drag from corner to corner.
  - Wend: progressive drag through each solved word path.
- Main action: `Solve & apply`, with a separate `Preview solution` option.
- `Board tools`: detect/select a board, apply the last solution, or clear the preview.
- `Preferences`: custom service address, input timing, Tango controls, and auto-close.
- In-page quick solve widget (`Solve <Game>`).

## Step 1: Start the Solver API (Choose One)

Choose **Online** under **Solve using** to use the hosted service without installing Python or Docker. The board image is sent to our API over HTTPS and is not archived. Existing local URLs are preserved; choose **Local / custom** and set **Preferences → Service address** to use your own service as described below. See [Vercel deployment](../docs/vercel.md).

The following options run the API on your computer.

### Option A: Uvicorn (port 8000)

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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
   - `https://www.linkedin.com/games/wend/`
2. Click the extension icon.
3. Choose `Online`, or `Local / custom` with a service address in `Preferences` (`8000` for Uvicorn or `18000` for Docker).
4. The game is detected from the active tab; change `Your game` if needed. Keep the whole board visible, including Wend's answer slots.
5. Click `Solve & apply` in the popup or `Solve <Game>` on the page. For a preview first, use `Preview solution`, then `Board tools → Apply last solution`.

## Troubleshooting

- If solve fails, check API health:

```bash
curl http://127.0.0.1:8000/health
# or Docker mode:
curl http://127.0.0.1:18000/health
```

- If quick widget does not appear, refresh the LinkedIn game page.
- If board detection misses once, use `Board tools → Select area` manually and reuse it.
- LinkedIn games run in an iframe; this extension includes frame-aware mapping for detection, overlay, and apply.
- Mini Sudoku disables Notes mode, waits for a complete, stable, readable grid, checks LinkedIn's cell indices and active-cell marker, focuses the keyboard-enabled grid (the cells themselves cannot take focus), and verifies each committed number before continuing. If a click or number is not accepted, it stops instead of replaying the solution or clicking guessed cells. A second apply request cannot run concurrently in the same game frame.
- After updating extension code, reload the extension and refresh existing LinkedIn tabs once so they use the updated content script.
- If Firefox shows `background.service_worker is currently disabled. Add background.scripts.`, remove and reload the temporary add-on from `extension/manifest.json` after pulling latest changes.
