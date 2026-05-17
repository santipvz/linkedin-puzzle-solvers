#!/usr/bin/env python3
from __future__ import annotations

import subprocess


COMMANDS: tuple[tuple[str, ...], ...] = (
    ("python3", "-m", "ruff", "check", "."),
    ("python3", "scripts/check_puzzle_registry_sync.py"),
    ("python3", "-m", "compileall", "-q", "services/solver_api/app", "games", "core", "scripts"),
    ("python3", "-m", "unittest", "discover", "-s", "services/solver_api/tests", "-p", "test_*.py"),
    ("python3", "scripts/smoke_check.py"),
    ("python3", "-m", "pytest", "games/patches_solver/tests/test_solver.py", "games/queen_solver/tests/test_solver.py"),
    ("python3", "scripts/api_endpoint_smoke.py"),
    ("node", "--check", "extension/background.js"),
    ("node", "--check", "extension/content.js"),
    ("node", "--check", "extension/popup.js"),
)


def main() -> int:
    for command in COMMANDS:
        print(f"$ {' '.join(command)}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return int(result.returncode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
