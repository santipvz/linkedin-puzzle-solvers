# Contributing

## Develop

Use Python 3.12 and Node 20+. Start work from `develop`:

```bash
git fetch origin
git switch develop
git pull --ff-only
git switch -c feature/my-change
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

For native OCR on Debian/Ubuntu, install `fonts-dejavu-core`, `fonts-liberation`, and `fonts-noto-core`. The [CI container](docs/ci.md) includes them.

Run the development API from the repository root:

```bash
uvicorn services.solver_api.app.main:app --reload --host 127.0.0.1 --port 8000
```

Use API URL `http://127.0.0.1:8000` in the [extension](extension/README.md).

## Validate

```bash
python3 scripts/quality_check.py
```

This runs architecture checks, lint, tests, and worker/API smoke checks. For apply changes, also test the affected game in the browser. See [CI](docs/ci.md) for the container command.

## Gitflow

| Branch | Purpose | PR target |
| --- | --- | --- |
| `main` | Released code | — |
| `develop` | Integration; default branch | — |
| `feature/*`, `bugfix/*` | Branch from `develop` | `develop` |
| `release/*` | Prepare a release from `develop` | `main`, then sync back to `develop` |
| `hotfix/*` | Urgent fix from `main` | `main`, then sync back to `develop` |

Use merge commits for releases and synchronization to preserve branch ancestry. CI checks PR branch names and targets. Follow the [release guide](docs/release.md) for versions and tags.

Only `main` and `develop` are permanent. GitHub automatically deletes topic branches after merge. Run `git fetch --prune` and delete the merged local branch with `git branch -d <branch>`.

## Submit

Use the issue and PR templates. Keep changes focused, explain the resulting behavior, and record validation. Follow the [architecture boundaries](docs/architecture.md); add a regression test for fixes. Never commit credentials or private captures.
