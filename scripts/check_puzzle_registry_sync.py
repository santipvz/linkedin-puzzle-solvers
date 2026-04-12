#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.puzzle_registry import PUZZLE_DEFINITIONS


def _backend_puzzle_keys() -> list[str]:
    return sorted(definition.key for definition in PUZZLE_DEFINITIONS)


def _extension_puzzle_keys() -> list[str]:
    registry_path = REPO_ROOT / "extension" / "puzzle_registry.js"
    content = registry_path.read_text(encoding="utf-8")
    keys = re.findall(r"\bkey\s*:\s*\"([a-z0-9_-]+)\"", content)
    return sorted(set(keys))


def main() -> int:
    backend = _backend_puzzle_keys()
    extension = _extension_puzzle_keys()

    if backend != extension:
        backend_set = set(backend)
        extension_set = set(extension)

        missing_in_extension = sorted(backend_set - extension_set)
        missing_in_backend = sorted(extension_set - backend_set)

        print("[error] puzzle registries are out of sync")
        print(f"  backend keys:   {backend}")
        print(f"  extension keys: {extension}")
        if missing_in_extension:
            print(f"  missing in extension: {missing_in_extension}")
        if missing_in_backend:
            print(f"  missing in backend:   {missing_in_backend}")
        return 1

    print(f"[ok] puzzle registries are in sync: {backend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
