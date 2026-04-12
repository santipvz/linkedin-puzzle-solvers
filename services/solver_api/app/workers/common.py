from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


def repo_root_for_worker(worker_file: str | Path) -> Path:
    return Path(worker_file).resolve().parents[4]


def game_root_for_worker(worker_file: str | Path, game_folder: str) -> Path:
    return repo_root_for_worker(worker_file) / "games" / game_folder


def ensure_sys_path(path: Path) -> None:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def run_worker_cli(
    argv: list[str],
    solve_fn: Callable[[Path], dict[str, Any]],
    worker_script: str,
    worker_label: str,
) -> int:
    if len(argv) != 2:
        print(f"Usage: {worker_script} <image_path>", file=sys.stderr)
        return 1

    image_path = Path(argv[1]).resolve()
    if not image_path.exists():
        print(f"Image file not found: {image_path}", file=sys.stderr)
        return 1

    try:
        result = solve_fn(image_path)
    except Exception as exc:
        print(f"{worker_label} worker crashed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0
