<p align="center"><img src="docs/assets/readme/logo.png" alt="LinkedIn Puzzle Solvers" width="160"></p>

# LinkedIn Puzzle Solvers

Solve **Queens, Tango, Mini Sudoku, Zip, Patches, and Wend** with a browser extension and a local API. The extension captures the board, previews the solution, and applies the moves.

[![CI](https://github.com/santipvz/linkedin-puzzle-solvers/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/santipvz/linkedin-puzzle-solvers/actions/workflows/ci.yml)

## Get started

1. Start the API from the repository root:

   ```bash
   mkdir -p datasets
   docker compose -f deploy/local/docker-compose.yml up -d --build
   ```

2. Load the extension:
   - **Chrome/Chromium:** open `chrome://extensions`, enable Developer mode, and load `extension/` unpacked.
   - **Firefox:** open `about:debugging#/runtime/this-firefox` and load `extension/manifest.json` as a temporary add-on.

3. Open a supported [LinkedIn game](https://www.linkedin.com/games/), set the extension API URL to **`http://127.0.0.1:18000`**, and click **Solve + Apply**.

The API health check is [localhost:18000/health](http://127.0.0.1:18000/health).

<details>
<summary>Demos</summary>

| Queens | Tango |
| --- | --- |
| ![Queens](docs/assets/readme/queens.gif) | ![Tango](docs/assets/readme/tango.gif) |
| **Mini Sudoku** | **Zip** |
| ![Mini Sudoku](docs/assets/readme/minisudoku.gif) | ![Zip](docs/assets/readme/zip.gif) |
| **Patches** | **Wend** |
| ![Patches](docs/assets/readme/patches.gif) | ![Wend](docs/assets/readme/wend.gif) |

</details>

## Documentation

- [Extension usage and troubleshooting](extension/README.md)
- [Docker configuration](deploy/local/README.md) · [API endpoints and settings](services/solver_api/README.md)
- [Contributing and Gitflow](CONTRIBUTING.md) · [Architecture](docs/architecture.md) · [Releases](docs/release.md)

MIT license. See [LICENSE](LICENSE).
