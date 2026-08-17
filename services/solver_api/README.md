# Solver API

FastAPI service that exposes solvers for Queens, Tango, Mini Sudoku, Zip, Patches, and Wend.

## Run Modes

You can run this API in two supported ways.

### Mode A: Local Uvicorn (recommended for development)

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### Mode B: Docker Compose (recommended for persistent local deployment)

From repository root:

```bash
cd deploy/local
cp .env.example .env
mkdir -p ../../datasets
docker compose up -d --build
```

Health check:

```bash
curl http://127.0.0.1:18000/health
```

See `deploy/local/README.md` for full operational commands.

## Endpoints

- `GET /health`
- `POST /solve/queens`
- `POST /solve/tango`
- `POST /solve/sudoku`
- `POST /solve/zip`
- `POST /solve/patches`
- `POST /solve/wend`

All solve endpoints accept multipart form data with field name `image`.

Example request:

```bash
curl -X POST \
  -F "image=@../../games/tango_solver/examples/sample1.png" \
  http://127.0.0.1:8000/solve/tango
```

If running in Docker mode, change port `8000` -> `18000`.

## Notes

- Workers run in isolated subprocesses by default with a hard timeout.
- Set `SOLVER_WORKER_MODE=inprocess` only for trusted development workloads; legacy import contexts serialize that mode.
- Solve responses are cached in memory by puzzle revision and image hash.
- Dataset capture is enabled for start-board requests by default.
- Default capture path: `datasets/<puzzle>/<YYYY-MM-DD>/`.
- Captures preserve the complete uploaded image so parser regressions remain reproducible.
- Disable capture with `DATASET_CAPTURE_ENABLED=0`.
- CORS defaults to `*`; override with `CORS_ALLOW_ORIGINS` (comma-separated) and optional `CORS_ALLOW_ORIGIN_REGEX`.
