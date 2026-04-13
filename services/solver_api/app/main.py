from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from .puzzle_registry import PUZZLE_DEFINITIONS, get_puzzle_definition


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[2]
WORKERS_DIR = APP_DIR / "workers"
DEFAULT_CAPTURE_DATASET_DIR = REPO_ROOT / "datasets"
CAPTURE_DATASET_DIR = Path(os.getenv("DATASET_CAPTURE_DIR") or DEFAULT_CAPTURE_DATASET_DIR).expanduser()
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 60
MAX_SOLVE_CACHE_ENTRIES = 96
DATASET_CAPTURE_ENABLED = os.getenv("DATASET_CAPTURE_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
CORS_ALLOW_ORIGINS_RAW = os.getenv("CORS_ALLOW_ORIGINS", "*")
CORS_ALLOW_ORIGIN_REGEX = (os.getenv("CORS_ALLOW_ORIGIN_REGEX") or "").strip() or None


def _parse_cors_origins(raw_value: str) -> list[str]:
    values = [part.strip() for part in str(raw_value).split(",") if part.strip()]
    if not values:
        return ["*"]
    if "*" in values:
        return ["*"]
    return values


CORS_ALLOW_ORIGINS = _parse_cors_origins(CORS_ALLOW_ORIGINS_RAW)


_solve_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()


app = FastAPI(
    title="LinkedIn Puzzle Solver API",
    version="0.1.0",
    description="Local API wrapper for Queens, Tango, Mini Sudoku, Zip, and Patches image solvers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_origin_regex=None if CORS_ALLOW_ORIGINS == ["*"] else CORS_ALLOW_ORIGIN_REGEX,
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
    return copy.deepcopy(cached)


def _cache_put(cache_key: str, value: dict[str, Any]) -> None:
    _solve_cache[cache_key] = copy.deepcopy(value)
    _solve_cache.move_to_end(cache_key)
    while len(_solve_cache) > MAX_SOLVE_CACHE_ENTRIES:
        _solve_cache.popitem(last=False)


def _should_recompute_cached_response(puzzle_name: str, cached: dict[str, Any]) -> bool:
    if puzzle_name != "queens" or not isinstance(cached, dict):
        return False

    if bool(cached.get("solved")):
        return False

    error_text = str(cached.get("error") or "").lower()
    if "cannot have a valid solution" not in error_text:
        return False

    details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
    iterations = int(details.get("iterations") or 0)
    board_size = int(cached.get("board_size") or 0)
    regions_detected = int(details.get("regions_detected") or 0)

    # Old queens pre-validation false negatives fail before backtracking starts.
    return iterations == 0 and board_size > 0 and regions_detected == board_size


def _extract_board_bbox(response: dict[str, Any]) -> dict[str, int] | None:
    details = response.get("details") if isinstance(response, dict) else None
    if not isinstance(details, dict):
        return None

    board_bbox = details.get("board_bbox")
    if not isinstance(board_bbox, dict):
        return None

    try:
        x = int(board_bbox.get("x", -1))
        y = int(board_bbox.get("y", -1))
        width = int(board_bbox.get("width", -1))
        height = int(board_bbox.get("height", -1))
    except (TypeError, ValueError):
        return None

    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return None

    return {"x": x, "y": y, "width": width, "height": height}


def _extract_board_only_image_payload(payload: bytes, response: dict[str, Any]) -> bytes:
    board_bbox = _extract_board_bbox(response)
    if board_bbox is None:
        return payload

    try:
        with Image.open(io.BytesIO(payload)) as image:
            image_width, image_height = image.size
            x1 = max(0, min(image_width - 1, int(board_bbox["x"])))
            y1 = max(0, min(image_height - 1, int(board_bbox["y"])))
            x2 = max(x1 + 1, min(image_width, int(board_bbox["x"] + board_bbox["width"])))
            y2 = max(y1 + 1, min(image_height, int(board_bbox["y"] + board_bbox["height"])))

            board = image.crop((x1, y1, x2, y2))
            output = io.BytesIO()
            board.save(output, format="PNG")
            return output.getvalue()
    except Exception:
        return payload


def _archive_board_capture(puzzle: str, payload: bytes, response: dict[str, Any], from_cache: bool) -> None:
    if not DATASET_CAPTURE_ENABLED:
        return

    digest = hashlib.sha256(payload).hexdigest()
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")

    target_dir = CAPTURE_DATASET_DIR / puzzle / day
    target_dir.mkdir(parents=True, exist_ok=True)

    image_path = target_dir / f"{digest}.png"
    metadata_path = target_dir / f"{digest}.json"

    if not image_path.exists():
        image_payload = _extract_board_only_image_payload(payload, response)
        image_path.write_bytes(image_payload)

    metadata: dict[str, Any] = {
        "puzzle": puzzle,
        "sha256": digest,
        "captured_at": now.isoformat(),
        "from_cache": bool(from_cache),
        "solved": bool(response.get("solved")),
        "error": response.get("error"),
        "board_size": response.get("board_size"),
        "details": response.get("details"),
    }

    if metadata_path.exists():
        try:
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

        seen_count = int(existing.get("seen_count") or 1)
        metadata["first_captured_at"] = existing.get("first_captured_at") or existing.get("captured_at") or metadata["captured_at"]
        metadata["seen_count"] = seen_count + 1
    else:
        metadata["first_captured_at"] = metadata["captured_at"]
        metadata["seen_count"] = 1

    metadata_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")


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


async def _solve_with_worker(
    worker_filename: str,
    image: UploadFile,
    puzzle_name: str,
    capture_board_start: bool,
) -> dict[str, Any]:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")

    payload = await _read_upload_bytes(image)
    cache_key = _cache_key_for_upload(puzzle_name, payload)
    cached = _cache_get(cache_key)
    if cached is not None and not _should_recompute_cached_response(puzzle_name, cached):
        response = cached
        from_cache = True
    else:
        temp_image_path = _write_temp_image(payload, image.filename)
        try:
            response = await asyncio.to_thread(_run_solver_worker, worker_filename, temp_image_path)
        finally:
            temp_image_path.unlink(missing_ok=True)

        _cache_put(cache_key, response)
        from_cache = False

    if capture_board_start:
        try:
            await asyncio.to_thread(_archive_board_capture, puzzle_name, payload, response, from_cache)
        except Exception:
            pass
    return response


def _should_capture_board_start(header_value: str | None) -> bool:
    if not header_value:
        return False
    return header_value.strip().lower() == "start"


def _build_solve_handler(puzzle_key: str):
    definition = get_puzzle_definition(puzzle_key)

    async def solve_handler(
        image: UploadFile = File(...),
        board_capture: str | None = Header(default=None, alias="X-Board-Capture"),
    ) -> dict[str, Any]:
        return await _solve_with_worker(
            definition.worker_filename,
            image,
            definition.key,
            capture_board_start=_should_capture_board_start(board_capture),
        )

    solve_handler.__name__ = f"solve_{definition.key}"
    return solve_handler


for puzzle_definition in PUZZLE_DEFINITIONS:
    app.post(
        puzzle_definition.endpoint_path,
        name=f"solve_{puzzle_definition.key}",
    )(_build_solve_handler(puzzle_definition.key))
