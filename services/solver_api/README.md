# Solver API

FastAPI service that exposes solvers for Queens, Tango, Mini Sudoku, Zip, and Patches.

## Run Modes

You can run this API in two supported ways.

### Mode A: Local Uvicorn (recommended for development)

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/solver_api/requirements.txt

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

All solve endpoints accept multipart form data with field name `image`.

Example request:

```bash
curl -X POST \
  -F "image=@../../games/tango_solver/examples/sample1.png" \
  http://127.0.0.1:8000/solve/tango
```

If running in Docker mode, change port `8000` -> `18000`.

## Notes

- Each puzzle solver runs in an isolated subprocess worker.
- Solve responses are cached by image hash in memory.
- Dataset capture is enabled for start-board requests by default.
- Default capture path: `datasets/<puzzle>/<YYYY-MM-DD>/`.
- Disable capture with `DATASET_CAPTURE_ENABLED=0`.
