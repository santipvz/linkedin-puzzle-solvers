# Release Guide

This project has two deliverables:

1. Local solver API + workers (Python)
2. Chrome extension package

## Pre-release checks

From repo root:

```bash
python -m pip install -r services/solver_api/requirements.txt
python -m compileall services/solver_api/app
python scripts/smoke_check.py
node --check extension/background.js
node --check extension/content.js
node --check extension/popup.js
```

## Prepare extension release

1. Update `extension/manifest.json` version.
2. Package extension directory:

```bash
cd extension
zip -r ../linkedin-puzzle-solver-extension.zip .
```

3. Upload the zip as a GitHub release asset (or Chrome Web Store package).

## Create GitHub release

1. Ensure `main` is clean and synced.
2. Create and push tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

3. Create release notes including:
   - Queens and Tango solve/apply support
   - Extension UX updates
   - API/solver changes

## CI notes

- CI workflow runs at `.github/workflows/ci.yml`.
- It validates Python modules, worker smoke checks, and extension script syntax.
