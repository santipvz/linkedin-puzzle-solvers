from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


APP_DIR = Path(__file__).resolve().parent
WORKERS_DIR = APP_DIR / "workers"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 60
MAX_SOLVE_CACHE_ENTRIES = 96


_solve_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()


app = FastAPI(
    title="LinkedIn Puzzle Solver API",
    version="0.1.0",
    description="Local API wrapper for Queens, Tango, Mini Sudoku, and Zip image solvers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    payload = await upload.read()

    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    if len(payload) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded image exceeds {MAX_UPLOAD_SIZE_BYTES} bytes.",
        )

    return payload


def _cache_key_for_upload(puzzle: str, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    return f"{puzzle}:{digest}"


def _cache_get(cache_key: str) -> dict[str, Any] | None:
    cached = _solve_cache.get(cache_key)
    if cached is None:
        return None

    _solve_cache.move_to_end(cache_key)
    return json.loads(json.dumps(cached))


def _cache_put(cache_key: str, value: dict[str, Any]) -> None:
    _solve_cache[cache_key] = json.loads(json.dumps(value))
    _solve_cache.move_to_end(cache_key)
    while len(_solve_cache) > MAX_SOLVE_CACHE_ENTRIES:
        _solve_cache.popitem(last=False)


def _write_temp_image(payload: bytes, filename: str | None) -> Path:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        suffix = ".png"

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="board_")
    try:
        handle.write(payload)
    finally:
        handle.close()

    return Path(handle.name)


def _run_solver_worker(worker_filename: str, image_path: Path) -> dict[str, Any]:
    worker_path = WORKERS_DIR / worker_filename
    if not worker_path.exists():
        raise HTTPException(status_code=500, detail=f"Worker not found: {worker_filename}")

    try:
        result = subprocess.run(
            [sys.executable, str(worker_path), str(image_path)],
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Solver timed out after {WORKER_TIMEOUT_SECONDS} seconds.",
        ) from exc

    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip() or "Unknown worker failure."
        raise HTTPException(status_code=500, detail=f"Worker execution failed: {error_output}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        sample = result.stdout.strip()[:600]
        raise HTTPException(status_code=500, detail=f"Worker produced invalid JSON: {sample}") from exc


async def _solve_with_worker(worker_filename: str, image: UploadFile, puzzle_name: str) -> dict[str, Any]:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")

    payload = await _read_upload_bytes(image)
    cache_key = _cache_key_for_upload(puzzle_name, payload)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    temp_image_path = _write_temp_image(payload, image.filename)
    try:
        response = await asyncio.to_thread(_run_solver_worker, worker_filename, temp_image_path)
    finally:
        temp_image_path.unlink(missing_ok=True)

    _cache_put(cache_key, response)
    return response


@app.post("/solve/queens")
async def solve_queens(image: UploadFile = File(...)) -> dict[str, Any]:
    return await _solve_with_worker("solve_queens_worker.py", image, "queens")


@app.post("/solve/tango")
async def solve_tango(image: UploadFile = File(...)) -> dict[str, Any]:
    return await _solve_with_worker("solve_tango_worker.py", image, "tango")


@app.post("/solve/sudoku")
async def solve_sudoku(image: UploadFile = File(...)) -> dict[str, Any]:
    return await _solve_with_worker("solve_sudoku_worker.py", image, "sudoku")


@app.post("/solve/zip")
async def solve_zip(image: UploadFile = File(...)) -> dict[str, Any]:
    return await _solve_with_worker("solve_zip_worker.py", image, "zip")
