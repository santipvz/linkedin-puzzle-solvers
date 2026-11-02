"""One reusable, killable child per API instance; changing games replaces it."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import threading
import time

from ..domain.errors import SolverBusy, SolverTimeout, WorkerFailure


class PersistentWorker:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self.worker_path: Path | None = None
        self.lock = threading.Lock()
        atexit.register(self.close)

    def close(self) -> None:
        process, self.process = self.process, None
        self.worker_path = None
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdin.close()
            process.stdout.close()

    def solve(self, worker_path: Path, image_path: Path, parsed_board: dict | None) -> dict:
        if not self.lock.acquire(blocking=False):
            raise SolverBusy("Solver is busy. Try again in a moment.")
        try:
            if self.worker_path != worker_path or self.process is None or self.process.poll() is not None:
                self.close()
                self.process = subprocess.Popen(
                    [sys.executable, "-u", str(Path(__file__).with_name("persistent_runner.py")), str(worker_path)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    env={**os.environ, "PYTHONPATH": os.pathsep.join(dict.fromkeys(
                        [path for path in sys.path if path] + os.environ.get("PYTHONPATH", "").split(os.pathsep)
                    ))},
                )
                self.worker_path = worker_path
            process = self.process
            deadline = time.monotonic() + self.timeout
            process.stdin.write((json.dumps({"image_path": str(image_path), "parsed_board": parsed_board}) + "\n").encode())
            process.stdin.flush()
            output = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while b"\n" not in output:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise SolverTimeout(f"Solver timed out after {self.timeout} seconds.")
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise WorkerFailure("Persistent worker exited without a response.")
                    output.extend(chunk)
            payload = json.loads(output)
            if "error" in payload:
                raise WorkerFailure(f"Worker execution failed: {payload['error']}")
            response = payload["response"]
            if not isinstance(response, dict):
                raise WorkerFailure("Worker returned an invalid response.")
            return response
        except (SolverTimeout, WorkerFailure):
            self.close()
            raise
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.close()
            raise WorkerFailure(f"Persistent worker failed: {exc}") from exc
        finally:
            self.lock.release()
