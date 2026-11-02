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

Wend also accepts an optional `parsed_board` form field containing JSON with `board` (a 5–8 square matrix of uppercase ASCII letters and null holes) and `lengths` (answer-slot lengths). The extension sends this only after a complete page read. The API validates it, includes it in the cache key, and forwards it to the isolated worker through stdin. Image-only clients keep the OCR pipeline. Both paths require a unique solution.

Example request:

```bash
curl -X POST \
  -F "image=@../../games/tango_solver/examples/sample1.png" \
  http://127.0.0.1:8000/solve/tango
```

If running in Docker mode, change port `8000` -> `18000`.

## Notes

- Local workers run in fresh isolated subprocesses by default with a hard timeout. Hosted workers default to `SOLVER_WORKER_MODE=persistent`: one reusable isolated child retains imports and OCR caches between solves of the same game. Changing games replaces the child to bound memory; timeout, crash or worker failure kills it, and the next request starts a new one. API shutdown closes it. Set `SOLVER_WORKER_MODE=subprocess` to restore fresh processes.
- Set `SOLVER_WORKER_MODE=inprocess` only for trusted development workloads; legacy import contexts serialize that mode.
- Solve responses are cached in memory by puzzle revision and image hash.
- Dataset capture is enabled for start-board requests by default.
- Default capture path: `datasets/<puzzle>/<YYYY-MM-DD>/`.
- Captures preserve the complete uploaded image so parser regressions remain reproducible.
- Disable capture with `DATASET_CAPTURE_ENABLED=0`.
- CORS defaults to `*`; override with `CORS_ALLOW_ORIGINS` (comma-separated) and optional `CORS_ALLOW_ORIGIN_REGEX`.

## Performance measurements

Run `python3 scripts/solver_benchmark.py --hosted --runs 5` to measure the tracked Sudoku, Patches, Zip and Wend captures with the online font set. Each puzzle starts with an empty temporary OCR cache, followed by fresh worker processes that reuse that disk cache. Add `--mode persistent` to measure reusable workers without the HTTP solution cache; both modes perform parsing and search on every run. Total timings run without instrumentation; an additional warm run uses cProfile to estimate pure search time separately. Measurements exclude network, serverless scheduling and browser gestures. Use `--json /tmp/solver-timings.json` to retain individual measurements.

Sudoku reuses rasterized glyph masks during OCR training, Patches derives shifted templates from one padded glyph, and Zip packs translated templates in NumPy batches. The template compatibility tests check pixel/bit equality, preserving recognition and search behavior.
