# Browser Extension

Browser extension for solving LinkedIn daily puzzles through the online or local solver API.

Install from the stable `main` branch or a release tag. `develop` contains work for the next release. See the [release guide](../docs/release.md) for packaging and distribution.

## Features

- Manual board selection on the active tab.
- Auto board detection (top page + iframe-aware).
- Solve via API endpoints for Queens, Tango, Mini Sudoku, Zip, Patches, Wend, and Sumbreak.
- Overlay preview for detected moves.
- Auto-apply support:
  - Queens: click-based input.
  - Tango: sun/moon click cycles.
  - Mini Sudoku: stable 36-cell grid detection and verified keyboard input; stops on unconfirmed writes.
  - Zip: start click + arrow keys.
  - Patches: rectangle drag from corner to corner.
  - Wend: progressive drag through each solved word path.
  - Sumbreak: tap the source tile, then the equal neighbour it merges into; each merge is verified before the next.
- Main action: `Solve & apply`, with a separate `Preview solution` option.
- `Board tools`: detect/select a board, apply the last solution, or clear the preview.
- `Preferences`: custom service address, input timing and auto-close.
- In-page quick solve widget (`Solve <Game>`), available on the first visit without opening the toolbar popup.

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
   - `https://www.linkedin.com/games/sumbreak/`
2. Click `Solve <Game>` directly on the page, or open the extension icon in Chrome’s toolbar for preview and preferences. No toolbar activation is required before using the page button.
3. Choose `Online`, or `Local / custom` with a service address in `Preferences` (`8000` for Uvicorn or `18000` for Docker).
4. The game is detected from the active tab; change `Your game` if needed. Keep the whole board visible, including Wend's answer slots.
5. Click `Solve & apply` in the popup or `Solve <Game>` on the page. For a preview first, use `Preview solution`, then `Board tools → Apply last solution`.

Chrome requires the `<all_urls>` host permission for capture from an in-page button without a prior toolbar grant. The extension checks that the target is an active supported HTTPS LinkedIn game before capturing. Content scripts remain restricted to LinkedIn. Chrome may ask you to accept expanded site access after updating; reload the extension and refresh the game tab.

## Input timing

Every game applies its solution at the same pace. **Move interval** (default 100 ms) is the time from the start of one move to the start of the next; a move is one queen, one Tango or Sudoku cell, one Patches rectangle, one Wend word or one Sumbreak merge. A path drawn in one stroke (the Zip path, a Wend word) advances one cell every 32 ms. Waits inside a move count toward the interval rather than being added after it, and the extension checks the game's confirmation every 10 ms. **Between clicks** (default 45 ms) only separates two clicks within the same move. These waits run in the browser, independently of the API solve time.

A move only takes longer than the interval when the game itself needs more time:

| Game | Move | Waits inside the move |
| --- | --- | --- |
| Queens | One queen | Two clicks, separated by the click delay. |
| Tango | One cell | One or two clicks; each is confirmed before the next. |
| Mini Sudoku | One cell | Select, at least 80 ms for the game to take keyboard input, type, confirm. |
| Zip | The whole path | A start click with at least 80 ms activation time, then one arrow key every 32 ms. |
| Patches | One rectangle | Drag, then up to 150 ms for the board to settle (the game drops drags that start too soon). |
| Wend | One word | The drag itself (8 ms per interpolation step), then the game locking the word. |
| Sumbreak | One merge | Two taps separated by the click delay, then the merged tile appearing. |

Mini Sudoku captures its outer board frame plus an 8 CSS-pixel margin. The inner grid remains the reference for locating cells when applying numbers.

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
- If Chrome invalidates an open game's extension context during an update, the widget stops polling and offers **Reload page** to load the new script.
- For Firefox, install the extracted Firefox package generated by `python3 scripts/package_extension.py --browser firefox`; the source manifest is kept in Chrome Manifest V3 format.
- After changing or reloading the extension, refresh existing LinkedIn tabs so their content scripts use the current extension context.
