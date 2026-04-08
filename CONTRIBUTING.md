# Contributing

Thanks for your interest in improving this project.

## Development Setup

1. Fork and clone the repository.
2. Create a feature branch from `main`.
3. Set up the solver API (Uvicorn mode recommended while developing).

```bash
git checkout -b feat/your-change-name
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/solver_api/requirements.txt
```

## Run the Project Locally

### API with Uvicorn

```bash
cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### API with Docker

```bash
cd deploy/local
cp .env.example .env
mkdir -p ../../datasets
docker compose up -d --build
```

## Validation Checklist

Before opening a PR, run these checks from repository root.

1. Smoke checks for all puzzle workers:

```bash
python3 scripts/smoke_check.py
```

2. Extension script syntax checks:

```bash
node --check extension/background.js
node --check extension/content.js
node --check extension/popup.js
```

3. Verify health endpoint for your selected API mode:

```bash
curl http://127.0.0.1:8000/health
# or Docker mode
curl http://127.0.0.1:18000/health
```

4. Manual browser test on at least one LinkedIn puzzle page.

## Pull Request Guidelines

- Keep changes focused and scoped.
- Add or update documentation when behavior changes.
- Use clear commit messages in imperative style (for example: `fix: improve sudoku apply targeting`).
- Include a short test note in your PR description (what you ran and the result).

## Reporting Issues

When filing an issue, include:

- Browser and version.
- OS and architecture.
- Puzzle type and URL.
- API mode (`uvicorn` or Docker).
- Steps to reproduce.
- Relevant logs and screenshots.

## Security

Do not commit secrets, tokens, or private endpoints.
If you discover a security issue, please report it privately before opening a public issue.
