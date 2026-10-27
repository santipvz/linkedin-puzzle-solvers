from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from ..domain.errors import SolverError, SolverTimeout, WorkerFailure
from ..domain.models import JsonDict


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_IMPORT_LOCK = threading.Lock()


class WorkerSolver:
    def __init__(self, worker_filenames: dict[str, str], workers_directory: Path, mode: str = "subprocess", timeout: int = 60) -> None:
        self.worker_filenames = dict(worker_filenames)
        self.workers_directory = workers_directory
        self.mode = mode
        self.timeout = timeout
        self._solve_functions: dict[str, Any] = {}

    def solve(self, puzzle: str, image: bytes, filename: str | None) -> JsonDict:
        path = self._write_temp_image(image, filename)
        try:
            response = self._run_solver_worker(self.worker_filenames[puzzle], path)
            if not isinstance(response, dict):
                raise WorkerFailure("Worker returned an invalid response.")
            return response
        finally:
            path.unlink(missing_ok=True)

    def _write_temp_image(self, payload: bytes, filename: str | None) -> Path:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            suffix = ".png"

        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="board_")
        try:
            handle.write(payload)
        finally:
            handle.close()

        return Path(handle.name)

    def _run_solver_worker_subprocess(self, worker_filename: str, image_path: Path) -> JsonDict:
        worker_path = self.workers_directory / worker_filename
        if not worker_path.exists():
            raise WorkerFailure(f"Worker not found: {worker_filename}")

        try:
            result = subprocess.run(
                [sys.executable, str(worker_path), str(image_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SolverTimeout(f"Solver timed out after {self.timeout} seconds.") from exc

        if result.returncode != 0:
            error_output = result.stderr.strip() or result.stdout.strip() or "Unknown worker failure."
            raise WorkerFailure(f"Worker execution failed: {error_output}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            sample = result.stdout.strip()[:600]
            raise WorkerFailure(f"Worker produced invalid JSON: {sample}") from exc

    def _worker_module_name_candidates(self, worker_filename: str) -> list[str]:
        module_stem = Path(worker_filename).stem
        if not module_stem:
            raise WorkerFailure(f"Invalid worker filename: {worker_filename}")
        return [
            f"services.solver_api.app.workers.{module_stem}",
            f"app.workers.{module_stem}",
            f"workers.{module_stem}",
        ]

    def _load_worker_solve_function(self, worker_filename: str) -> Any:
        solve_fn = self._solve_functions.get(worker_filename)
        if solve_fn is not None:
            return solve_fn

        module = None
        last_error: Exception | None = None
        for module_name in self._worker_module_name_candidates(worker_filename):
            try:
                module = importlib.import_module(module_name)
                break
            except ModuleNotFoundError as exc:
                last_error = exc
                continue

        if module is None:
            if last_error is not None:
                raise last_error
            raise WorkerFailure(f"Could not import worker module: {worker_filename}")

        solve_fn = getattr(module, "solve", None)
        if not callable(solve_fn):
            raise WorkerFailure(f"Worker has no solve function: {worker_filename}")

        self._solve_functions[worker_filename] = solve_fn
        return solve_fn

    def _run_solver_worker_inprocess(self, worker_filename: str, image_path: Path) -> JsonDict:
        worker_path = self.workers_directory / worker_filename
        if not worker_path.exists():
            raise WorkerFailure(f"Worker not found: {worker_filename}")

        # Game projects all expose modules under the name `src`, so imports are
        # process-global and must not overlap across concurrent solves.
        with _IMPORT_LOCK:
            try:
                solve_fn = self._load_worker_solve_function(worker_filename)
                response = solve_fn(image_path)
            except SolverError:
                raise
            except Exception as exc:
                raise WorkerFailure(f"Worker execution failed: {exc}") from exc

        if not isinstance(response, dict):
            raise WorkerFailure("Worker returned an invalid response.")

        return response

    def _run_solver_worker(self, worker_filename: str, image_path: Path) -> JsonDict:
        if self.mode in {"subprocess", "process", "isolated"}:
            return self._run_solver_worker_subprocess(worker_filename, image_path)
        return self._run_solver_worker_inprocess(worker_filename, image_path)
