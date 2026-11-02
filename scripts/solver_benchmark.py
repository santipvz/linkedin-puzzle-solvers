#!/usr/bin/env python3
"""Profile real isolated workers, separating search from OCR and process setup."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pstats
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.puzzle_registry import get_puzzle_definition
from services.solver_api.app.adapters.workers import WorkerSolver


def benchmark(puzzle: str, runs: int, hosted: bool, mode: str = "subprocess") -> dict:
    definition = get_puzzle_definition(puzzle)
    solver_files = {
        "sudoku": "mini_sudoku_solver.py", "patches": "patches_solver.py",
        "zip": "zip_solver.py", "wend": "wend_solver.py",
    }
    measurements = []
    command = [sys.executable, str(REPO_ROOT / "services/solver_api/app/workers" / definition.worker_filename),
               str(REPO_ROOT / definition.sample_image)]
    # A fresh cache directory makes the first invocation genuinely cold. Later
    # invocations reuse either disk caches or the persistent process itself.
    with tempfile.TemporaryDirectory(prefix=f"solver_benchmark_{puzzle}_") as tmp:
        env = {**os.environ, "TMPDIR": tmp, "SOLVER_BUNDLED_FONTS": "1" if hosted else "0"}
        for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            env[name] = "1"
        worker = WorkerSolver({puzzle: definition.worker_filename}, REPO_ROOT / "services/solver_api/app/workers", mode=mode)
        image = (REPO_ROOT / definition.sample_image).read_bytes()
        try:
            with patch.dict(os.environ, env):
                for index in range(runs + 1):
                    started = time.perf_counter()
                    # Call the worker directly, bypassing the HTTP solution cache.
                    payload = worker.solve(puzzle, image, "board.png")
                    elapsed = (time.perf_counter() - started) * 1000
                    if not payload.get("solved"):
                        raise RuntimeError(f"{puzzle}: {payload.get('error')}")
                    measurements.append({"phase": "cold" if index == 0 else "warm", "total_ms": elapsed})
        finally:
            worker.close()
        # Profile separately so vectorization speedups do not get inflated by
        # the profiler charging more overhead to the old Python loops.
        profile = Path(tmp) / "worker.prof"
        subprocess.run(
            [sys.executable, "-m", "cProfile", "-o", str(profile), *command[1:]],
            env=env, cwd=REPO_ROOT, capture_output=True, text=True, timeout=90, check=True,
        )
        stats = pstats.Stats(str(profile)).stats
        search_ms = sum(
            data[3] * 1000 for (filename, _line, function), data in stats.items()
            if Path(filename).name == solver_files[puzzle] and function == "solve"
        )
    return {
        "puzzle": puzzle, "fonts": "bundled" if hosted else "local", "mode": mode,
        "cold_total_ms": measurements[0]["total_ms"],
        "warm_total_ms": statistics.median(item["total_ms"] for item in measurements[1:]),
        "warm_search_ms": search_ms,
        "runs": measurements,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puzzles", nargs="+", choices=("sudoku", "patches", "zip", "wend"), default=["sudoku", "patches", "zip", "wend"])
    parser.add_argument("--runs", type=int, default=3, help="Warm subprocess runs after one cold run.")
    parser.add_argument("--hosted", action="store_true", help="Use the bundled fonts used by the online API.")
    parser.add_argument("--mode", choices=("subprocess", "persistent"), default="subprocess", help="Compare fresh workers with reusable workers.")
    parser.add_argument("--json", type=Path, help="Save full measurements to this JSON file.")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    print(f"Local {args.mode} workers; excludes network and browser application. Search is profiled separately.")
    print(f"{'Puzzle':<10} {'Cold (ms)':>12} {'Warm (ms)':>12} {'Search (ms)':>12}", flush=True)
    results = []
    for puzzle in args.puzzles:
        result = benchmark(puzzle, args.runs, args.hosted, args.mode)
        results.append(result)
        print(f"{puzzle:<10} {result['cold_total_ms']:>12.1f} {result['warm_total_ms']:>12.1f} {result['warm_search_ms']:>12.2f}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
