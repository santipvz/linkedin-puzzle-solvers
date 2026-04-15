from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Protocol, TypeAlias, TypedDict


JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)
JsonDict: TypeAlias = dict[str, JsonValue]


class _CapturedLogStream(Protocol):
    def getvalue(self) -> str: ...


class BoardBBox(TypedDict):
    x: int
    y: int
    width: int
    height: int


def repo_root_for_worker(worker_file: str | Path) -> Path:
    return Path(worker_file).resolve().parents[4]


def game_root_for_worker(worker_file: str | Path, game_folder: str) -> Path:
    return repo_root_for_worker(worker_file) / "games" / game_folder


def ensure_sys_path(path: Path) -> None:
    path_str = str(path)
    if path_str in sys.path:
        sys.path.remove(path_str)
    sys.path.insert(0, path_str)


def activate_game_import_context(game_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "src" or module_name.startswith("src."):
            del sys.modules[module_name]

    ensure_sys_path(game_root)


def run_worker_cli(
    argv: list[str],
    solve_fn: Callable[[Path], JsonDict],
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


def attach_captured_logs(response: JsonDict, captured_logs: _CapturedLogStream, max_chars: int = 1200) -> None:
    logs_value = str(captured_logs.getvalue()).strip()
    if logs_value:
        response["logs"] = logs_value[:max_chars]
