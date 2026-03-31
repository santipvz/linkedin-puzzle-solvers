# Solver API

Local FastAPI wrapper around the Queens, Tango, Mini Sudoku, and Zip solvers.

## Run

From repo root:

```bash
pip install -r services/solver_api/requirements.txt
cd services/solver_api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Endpoints

- `GET /health`
- `POST /solve/queens`
- `POST /solve/tango`
- `POST /solve/sudoku`
- `POST /solve/zip`

All solve endpoints expect multipart form data with one field named `image`.

Example:

```bash
curl -X POST \
  -F "image=@../../games/tango_solver/examples/sample1.png" \
  http://127.0.0.1:8000/solve/tango
```

## Notes

- The API runs each puzzle solver in an isolated subprocess worker to avoid module path collisions.
- Solve responses are cached by image hash in-memory for faster repeated solves.
- Board captures are saved for start-board requests only (not intermediate search attempts).
- Capture path defaults to `datasets/<puzzle>/<YYYY-MM-DD>/` and can be changed with `DATASET_CAPTURE_DIR`.
- Set `DATASET_CAPTURE_ENABLED=0` to disable dataset capture.
- This service is intended for local usage from the browser extension.
