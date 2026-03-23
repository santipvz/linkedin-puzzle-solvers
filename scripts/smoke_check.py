#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_worker(worker_path: Path, image_path: Path, puzzle_name: str, expected_board_size: int) -> None:
    result = subprocess.run(
        [sys.executable, str(worker_path), str(image_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Worker failed: "
            f"{worker_path.name}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    output_lines = result.stdout.strip().splitlines()
    if not output_lines:
        raise RuntimeError(f"Worker produced no JSON output: {worker_path.name}")

    payload = json.loads(output_lines[-1])

    if payload.get("puzzle") != puzzle_name:
        raise RuntimeError(
            f"Unexpected puzzle name from {worker_path.name}: "
            f"{payload.get('puzzle')} (expected {puzzle_name})"
        )

    if int(payload.get("board_size") or 0) != expected_board_size:
        raise RuntimeError(
            f"Unexpected board size from {worker_path.name}: "
            f"{payload.get('board_size')} (expected {expected_board_size})"
        )

    if not payload.get("solved"):
        raise RuntimeError(
            f"Worker returned unsolved payload for {worker_path.name}: "
            f"error={payload.get('error')}"
        )

    print(
        f"[ok] {worker_path.name}: solved={payload.get('solved')} "
        f"board_size={payload.get('board_size')}"
    )


def main() -> int:
    queens_worker = REPO_ROOT / "services" / "solver_api" / "app" / "workers" / "solve_queens_worker.py"
    queens_sample = REPO_ROOT / "games" / "queen_solver" / "examples" / "sample1.png"

    tango_worker = REPO_ROOT / "services" / "solver_api" / "app" / "workers" / "solve_tango_worker.py"
    tango_sample = REPO_ROOT / "games" / "tango_solver" / "examples" / "sample1.png"

    sudoku_worker = REPO_ROOT / "services" / "solver_api" / "app" / "workers" / "solve_sudoku_worker.py"
    sudoku_sample = REPO_ROOT / "games" / "sudoku_solver" / "examples" / "sample1.png"

    run_worker(queens_worker, queens_sample, "queens", expected_board_size=9)
    run_worker(tango_worker, tango_sample, "tango", expected_board_size=6)

    if sudoku_sample.exists():
        run_worker(sudoku_worker, sudoku_sample, "sudoku", expected_board_size=6)
    else:
        print("[skip] solve_sudoku_worker.py: sample image not found at games/sudoku_solver/examples/sample1.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
