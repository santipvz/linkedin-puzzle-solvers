# Interface assets

`logo.png` is an unchanged copy of `docs/assets/readme/logo.png`.

The six game icons in `games/` are original LinkedIn assets, copied unchanged from the public [LinkedIn Games page](https://www.linkedin.com/games/). Their source URLs and retrieval date are recorded in `games/sources.json`. These assets belong to their respective owners; the repository's MIT license does not grant rights to LinkedIn's artwork or trademarks.

All images are bundled with the extension. The interface does not request them from LinkedIn's CDN at runtime.

The SVGs in `pieces/` contain the original Queens crown and Tango sun/moon artwork extracted from rendered game cells. Their computed paint styles are inlined so the pieces render identically without depending on LinkedIn's CSS. See `pieces/sources.json` for provenance. Sudoku previews use the live game's number typography.

The installation icons (`icon16.png`, `icon32.png`, `icon48.png`, `icon128.png`) are rasterizations of the project-owned `icon.svg`, adapted from the independent puzzle-piece design in `docs/chrome-web-store/brand-proposal.svg`. They are bundled at native browser sizes; no external assets are fetched. To regenerate with ImageMagick, run `convert -background none extension/assets/icon.svg -resize 16x16 extension/assets/icon16.png` and repeat for 32, 48 and 128.
