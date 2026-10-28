<p align="center">
  <img src="docs/assets/readme/logo.png" alt="LinkedIn Puzzle Solvers logo" width="240">
</p>

<h1 align="center">LinkedIn Puzzle Solvers</h1>

<p align="center">
  <strong>Daily LinkedIn puzzles, solved locally.</strong>
  <br>
  Browser extension + FastAPI solver service powered by computer vision and puzzle-specific automation.
</p>

<p align="center">
  <a href="https://github.com/santipvz/linkedin-puzzle-solvers/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/santipvz/linkedin-puzzle-solvers/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-local_api-009688?logo=fastapi&logoColor=white">
  <img alt="Browser Extension" src="https://img.shields.io/badge/Browser-extension-4285F4?logo=googlechrome&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green">
</p>

<p align="center">
  <a href="https://github.com/santipvz/linkedin-puzzle-solvers/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/santipvz/linkedin-puzzle-solvers?style=social"></a>
  <a href="https://github.com/santipvz/linkedin-puzzle-solvers/fork"><img alt="GitHub forks" src="https://img.shields.io/github/forks/santipvz/linkedin-puzzle-solvers?style=social"></a>
  <a href="https://github.com/santipvz/linkedin-puzzle-solvers/issues"><img alt="GitHub issues" src="https://img.shields.io/github/issues/santipvz/linkedin-puzzle-solvers?logo=github"></a>
  <a href="https://github.com/santipvz/linkedin-puzzle-solvers/pulls"><img alt="GitHub pull requests" src="https://img.shields.io/github/issues-pr/santipvz/linkedin-puzzle-solvers?logo=github"></a>
</p>

<p align="center">
  <img alt="Queens" src="https://img.shields.io/badge/Queens-0A66C2?style=for-the-badge">
  <img alt="Tango" src="https://img.shields.io/badge/Tango-7C3AED?style=for-the-badge">
  <img alt="Mini Sudoku" src="https://img.shields.io/badge/Mini%20Sudoku-16A34A?style=for-the-badge">
  <img alt="Zip" src="https://img.shields.io/badge/Zip-F97316?style=for-the-badge">
  <img alt="Patches" src="https://img.shields.io/badge/Patches-E11D48?style=for-the-badge">
  <img alt="Wend" src="https://img.shields.io/badge/Wend-14B8A6?style=for-the-badge">
</p>

<p align="center">
  <img src="docs/assets/readme/solver-divider.svg" width="100%" alt="Animated divider">
</p>

## Demo Gallery

<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td width="50%">
      <h3 align="center">Queens</h3>
      <img src="docs/assets/readme/queens.gif" alt="Queens solver demo">
    </td>
    <td width="50%">
      <h3 align="center">Tango</h3>
      <img src="docs/assets/readme/tango.gif" alt="Tango solver demo">
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3 align="center">Mini Sudoku</h3>
      <img src="docs/assets/readme/minisudoku.gif" alt="Mini Sudoku solver demo">
    </td>
    <td width="50%">
      <h3 align="center">Zip</h3>
      <img src="docs/assets/readme/zip.gif" alt="Zip solver demo">
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3 align="center">Patches</h3>
      <img src="docs/assets/readme/patches.gif" alt="Patches solver demo">
    </td>
    <td width="50%">
      <h3 align="center">Wend</h3>
      <img src="docs/assets/readme/wend.gif" alt="Wend solver demo">
    </td>
  </tr>
</table>

<p align="center">
  <img src="docs/assets/readme/solver-divider.svg" width="100%" alt="Animated divider">
</p>


## Get started

Use the stable `main` branch or a release tag. `develop` contains work for the next release.

For online solving, load the extension as in step 2 and select **Online** in its popup. No local API is needed; the board image is sent to our hosted service. For local processing, follow all three steps below.

1. Start the API from the repository root:

   ```bash
   mkdir -p datasets
   docker compose -f deploy/local/docker-compose.yml up -d --build
   ```

2. Load the extension:
   - **Chrome/Chromium:** open `chrome://extensions`, enable Developer mode, and load `extension/` unpacked.
   - **Firefox:** open `about:debugging#/runtime/this-firefox` and load `extension/manifest.json` as a temporary add-on.

3. Open a supported [LinkedIn game](https://www.linkedin.com/games/), choose **Local / custom**, set **Preferences → Service address** to **`http://127.0.0.1:18000`**, and click **Solve & apply**.

The API health check is [localhost:18000/health](http://127.0.0.1:18000/health).

## Documentation

- [Extension usage and troubleshooting](extension/README.md)
- [Docker configuration](deploy/local/README.md) · [Vercel deployment](docs/vercel.md) · [API endpoints and settings](services/solver_api/README.md)
- [Contributing and Gitflow](CONTRIBUTING.md) · [Architecture](docs/architecture.md) · [Releases](docs/release.md)

MIT license. See [LICENSE](LICENSE).
