"""Reusable, killable children: one per game, kept warm up to a small limit."""
from __future__ import annotations

from collections import OrderedDict
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
    """A single child process serving one game worker over JSON lines."""

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


class PersistentWorkerPool:
    """Keeps one warm child per game so switching games does not pay start-up again.

    Each child still holds only its own game's imports and OCR caches. The least
    recently used idle child is closed once more than ``max_workers`` are alive.
    """

    def __init__(self, timeout: float, max_workers: int = 8) -> None:
        self.timeout = timeout
        self.max_workers = max(1, int(max_workers))
        self.children: OrderedDict[Path, PersistentWorker] = OrderedDict()
        self._lock = threading.Lock()
        atexit.register(self.close)

    def close(self) -> None:
        with self._lock:
            children = list(self.children.values())
            self.children.clear()
        for child in children:
            child.close()

    def solve(self, worker_path: Path, image_path: Path, parsed_board: dict | None) -> dict:
        with self._lock:
            child = self.children.get(worker_path)
            if child is None:
                child = PersistentWorker(self.timeout)
                self.children[worker_path] = child
            self.children.move_to_end(worker_path)
            evicted = self._evict_idle_locked(keep=worker_path)
        for old in evicted:
            old.close()
        return child.solve(worker_path, image_path, parsed_board)

    def _evict_idle_locked(self, keep: Path) -> list[PersistentWorker]:
        evicted: list[PersistentWorker] = []
        for path in list(self.children):
            if len(self.children) <= self.max_workers:
                break
            if path == keep:
                continue
            child = self.children[path]
            # Never kill a child that is answering another request.
            if child.lock.acquire(blocking=False):
                child.lock.release()
                del self.children[path]
                evicted.append(child)
        return evicted
