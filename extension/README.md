# Browser Extension (Scaffold)

Chrome extension that connects to the local solver API.

## Features in this scaffold

- Manual board region selection on the active tab
- Auto board region detection heuristic (top page and iframe-aware)
- Board screenshot capture and crop via extension background worker
- Solve request to local API (`/solve/queens` or `/solve/tango`)
- Visual overlay for both puzzle types
- Auto-apply support for Queens (2 clicks per cell)
- Auto-apply support for Tango (1 left click for sun, 2 left clicks for moon)
- One-click `Solve + Apply` action in popup
- Apply settings: auto-close, click delays, Tango input mode
- In-page quick widget that auto-detects game type and runs solve+apply in one click


## Load in Chrome

1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select this folder: `extension/`
5. Enable `Allow in incognito` if you want to test in incognito mode

## Usage

1. Start the local API at `http://127.0.0.1:8000`
2. Open one of the puzzle pages in your browser:
   - `https://www.linkedin.com/games/queens/`
   - `https://www.linkedin.com/games/tango/`
3. Click extension icon
4. Choose puzzle type
5. Use `Select Board` (or `Auto Detect`)
6. Click `Solve`
7. Click `Apply` or `Solve + Apply`

`Solve` shows overlay preview. `Solve + Apply` skips preview markers and directly applies moves.

## Faster flow (in-page)

On LinkedIn Queens/Tango pages, a small `Puzzle Quick Solve` widget appears on the page.
Click `Solve <Game>` and the extension auto-detects the game and board, solves, and applies.

After `Apply`, overlays are cleared. Popup auto-close can be toggled in settings.

Tango apply strategy uses solver encoding `0 = moon`, `1 = sun`.

## Notes for LinkedIn pages

- The `/games/*` pages host the game inside an iframe; this extension handles frame-aware overlay and apply.
- If auto-detection misses the board, use manual `Select Board` once and keep solving from there.
