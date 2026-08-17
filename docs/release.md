# Release Guide

This project has two deliverables:

1. Local solver API + workers (Python)
2. Chrome extension package

## Pre-release checks

From repo root:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/quality_check.py
docker build -f deploy/local/Dockerfile -t linkedin-puzzle-solvers-release .
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
   - Queens, Tango, Mini Sudoku, Zip, Patches, and Wend solve/apply support
   - Extension UX updates
   - API/solver changes

## CI notes

- CI workflow runs at `.github/workflows/ci.yml`.
- It validates linting, Python tests/modules, worker and API smoke checks, registry consistency, and extension syntax.
