#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.puzzle_registry import PUZZLE_DEFINITIONS


WORKERS_DIR = REPO_ROOT / "services" / "solver_api" / "app" / "workers"


def run_worker(
    worker_path: Path,
    image_path: Path,
    puzzle_name: str,
    expected_board_size: int,
    sample_label: str | None = None,
) -> None:
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

    sample_suffix = f" sample={sample_label}" if sample_label else ""
    print(
        f"[ok] {worker_path.name}: solved={payload.get('solved')} "
        f"board_size={payload.get('board_size')}{sample_suffix}"
    )


def main() -> int:
    for definition in PUZZLE_DEFINITIONS:
        worker_path = WORKERS_DIR / definition.worker_filename
        for sample_image in definition.all_smoke_samples:
            sample_path = REPO_ROOT / sample_image

            if not sample_path.exists():
                message = (
                    f"[skip] {definition.worker_filename}: sample image not found at {sample_image}"
                )
                if definition.sample_required:
                    raise RuntimeError(message)
                print(message)
                continue

            run_worker(
                worker_path=worker_path,
                image_path=sample_path,
                puzzle_name=definition.key,
                expected_board_size=int(definition.expected_board_size),
                sample_label=sample_path.name,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
