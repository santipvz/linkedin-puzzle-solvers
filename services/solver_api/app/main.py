from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .puzzle_registry import PUZZLE_DEFINITIONS, get_puzzle_definition
from .response_schemas import SolverResponse
from .workers.common import JsonDict


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
WORKER_MODE = os.getenv("SOLVER_WORKER_MODE", "subprocess").strip().lower()


def _parse_cors_origins(raw_value: str) -> list[str]:
    values = [part.strip() for part in str(raw_value).split(",") if part.strip()]
    if not values:
        return ["*"]
    if "*" in values:
        return ["*"]
    return values


CORS_ALLOW_ORIGINS = _parse_cors_origins(CORS_ALLOW_ORIGINS_RAW)


_solve_cache: OrderedDict[str, JsonDict] = OrderedDict()
_worker_import_lock = threading.Lock()
_capture_lock = threading.Lock()
_worker_solve_functions: dict[str, Any] = {}


app = FastAPI(
    title="LinkedIn Puzzle Solver API",
    version="0.1.0",
    description="Local API wrapper for Queens, Tango, Mini Sudoku, Zip, Patches, and Wend image solvers.",
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


def _cache_key_for_upload(puzzle: str, cache_revision: int, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    return f"{puzzle}:{cache_revision}:{digest}"


def _cache_get(cache_key: str) -> JsonDict | None:
    cached = _solve_cache.get(cache_key)
    if cached is None:
        return None

    _solve_cache.move_to_end(cache_key)
    return copy.deepcopy(cached)


def _cache_put(cache_key: str, value: JsonDict) -> None:
    _solve_cache[cache_key] = copy.deepcopy(value)
    _solve_cache.move_to_end(cache_key)
    while len(_solve_cache) > MAX_SOLVE_CACHE_ENTRIES:
        _solve_cache.popitem(last=False)


def _should_recompute_cached_response(puzzle_name: str, cached: JsonDict) -> bool:
    if not isinstance(cached, dict):
        return False

    if puzzle_name == "tango":
        board_size = int(cached.get("board_size") or 0)
        details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
        parse_reliable = details.get("parse_reliable")
        fixed_count = int(details.get("fixed_count") or 0)
        constraint_count = int(details.get("constraint_count") or 0)

        if board_size != 6:
            return True
        if parse_reliable is None:
            return True
        if not bool(cached.get("solved")) and fixed_count < 4 and constraint_count >= 2:
            return True

        return False

    if puzzle_name == "patches":
        details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
        return details.get("parse_reliable") is False

    if puzzle_name != "queens":
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


def _make_dataset_path_editable(path: Path) -> None:
    try:
        repo_stat = REPO_ROOT.stat()
        os.chown(path, repo_stat.st_uid, repo_stat.st_gid)
    except (AttributeError, OSError, PermissionError):
        pass

    try:
        if path.is_dir():
            path.chmod(0o775)
        else:
            path.chmod(0o664)
    except (OSError, PermissionError):
        pass


def _image_suffix(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith(b"BM"):
        return ".bmp"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return ".webp"
    return ".img"


def _archive_board_capture(puzzle: str, payload: bytes, response: JsonDict, from_cache: bool) -> None:
    with _capture_lock:
        _archive_board_capture_unlocked(puzzle, payload, response, from_cache)


def _archive_board_capture_unlocked(puzzle: str, payload: bytes, response: JsonDict, from_cache: bool) -> None:
    if not DATASET_CAPTURE_ENABLED:
        return

    digest = hashlib.sha256(payload).hexdigest()
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")

    target_dir = CAPTURE_DATASET_DIR / puzzle / day
    target_dir.mkdir(parents=True, exist_ok=True)
    for directory in (CAPTURE_DATASET_DIR, CAPTURE_DATASET_DIR / puzzle, target_dir):
        _make_dataset_path_editable(directory)

    image_path = target_dir / f"{digest}{_image_suffix(payload)}"
    metadata_path = target_dir / f"{digest}.json"

    existing_digest = hashlib.sha256(image_path.read_bytes()).hexdigest() if image_path.exists() else None
    if existing_digest != digest:
        image_temp_path = image_path.with_suffix(f"{image_path.suffix}.tmp")
        image_temp_path.write_bytes(payload)
        image_temp_path.replace(image_path)
        _make_dataset_path_editable(image_path)
    artifact_digest = hashlib.sha256(image_path.read_bytes()).hexdigest()

    metadata: dict[str, Any] = {
        "puzzle": puzzle,
        "sha256": digest,
        "original_sha256": digest,
        "artifact_sha256": artifact_digest,
        "artifact_filename": image_path.name,
        "captured_at": now.isoformat(),
        "from_cache": bool(from_cache),
        "solved": bool(response.get("solved")),
        "error": response.get("error"),
        "board_size": response.get("board_size"),
        "details": response.get("details"),
        "words": response.get("words"),
    }

    if metadata_path.exists():
        try:
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            existing = {}

        seen_count = int(existing.get("seen_count") or 1)
        metadata["first_captured_at"] = existing.get("first_captured_at") or existing.get("captured_at") or metadata["captured_at"]
        metadata["seen_count"] = seen_count + 1
    else:
        metadata["first_captured_at"] = metadata["captured_at"]
        metadata["seen_count"] = 1

    metadata_temp_path = metadata_path.with_suffix(".json.tmp")
    metadata_temp_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
    metadata_temp_path.replace(metadata_path)
    _make_dataset_path_editable(metadata_path)


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


def _run_solver_worker_subprocess(worker_filename: str, image_path: Path) -> JsonDict:
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


def _worker_module_name_candidates(worker_filename: str) -> list[str]:
    module_stem = Path(worker_filename).stem
    if not module_stem:
        raise HTTPException(status_code=500, detail=f"Invalid worker filename: {worker_filename}")
    return [
        f"services.solver_api.app.workers.{module_stem}",
        f"app.workers.{module_stem}",
        f"workers.{module_stem}",
    ]


def _load_worker_solve_function(worker_filename: str) -> Any:
    solve_fn = _worker_solve_functions.get(worker_filename)
    if solve_fn is not None:
        return solve_fn

    module = None
    last_error: Exception | None = None
    for module_name in _worker_module_name_candidates(worker_filename):
        try:
            module = importlib.import_module(module_name)
            break
        except ModuleNotFoundError as exc:
            last_error = exc
            continue

    if module is None:
        if last_error is not None:
            raise last_error
        raise HTTPException(status_code=500, detail=f"Could not import worker module: {worker_filename}")

    solve_fn = getattr(module, "solve", None)
    if not callable(solve_fn):
        raise HTTPException(status_code=500, detail=f"Worker has no solve function: {worker_filename}")

    _worker_solve_functions[worker_filename] = solve_fn
    return solve_fn


def _run_solver_worker_inprocess(worker_filename: str, image_path: Path) -> JsonDict:
    worker_path = WORKERS_DIR / worker_filename
    if not worker_path.exists():
        raise HTTPException(status_code=500, detail=f"Worker not found: {worker_filename}")

    # Game projects all expose modules under the name `src`, so imports are
    # process-global and must not overlap across concurrent solves.
    with _worker_import_lock:
        solve_fn = _load_worker_solve_function(worker_filename)
        try:
            response = solve_fn(image_path)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Worker execution failed: {exc}") from exc

    if not isinstance(response, dict):
        raise HTTPException(status_code=500, detail="Worker returned an invalid response.")

    return response


def _run_solver_worker(worker_filename: str, image_path: Path) -> JsonDict:
    if WORKER_MODE in {"subprocess", "process", "isolated"}:
        return _run_solver_worker_subprocess(worker_filename, image_path)
    return _run_solver_worker_inprocess(worker_filename, image_path)


async def _solve_with_worker(
    worker_filename: str,
    image: UploadFile,
    puzzle_name: str,
    cache_revision: int,
    capture_board_start: bool,
) -> JsonDict:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")

    payload = await _read_upload_bytes(image)
    cache_key = _cache_key_for_upload(puzzle_name, cache_revision, payload)
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
        except (OSError, ValueError, TypeError) as exc:
            print(f"Board capture archive skipped: {exc}", file=sys.stderr)
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
    ) -> SolverResponse | JsonDict:
        return await _solve_with_worker(
            definition.worker_filename,
            image,
            definition.key,
            definition.cache_revision,
            capture_board_start=_should_capture_board_start(board_capture),
        )

    solve_handler.__name__ = f"solve_{definition.key}"
    return solve_handler


for puzzle_definition in PUZZLE_DEFINITIONS:
    app.post(
        puzzle_definition.endpoint_path,
        name=f"solve_{puzzle_definition.key}",
        response_model=None,
    )(_build_solve_handler(puzzle_definition.key))
