#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.main import app


SAMPLES: tuple[tuple[str, str], ...] = (
    ("queens", "games/queen_solver/examples/sample1.png"),
    ("tango", "games/tango_solver/examples/sample1.png"),
    ("patches", "games/patches_solver/examples/sample1.png"),
)


def main() -> int:
    client = TestClient(app)

    for puzzle, sample_path in SAMPLES:
        absolute_path = REPO_ROOT / sample_path
        if not absolute_path.exists():
            print(f"[skip] {puzzle}: missing sample {sample_path}")
            continue

        with absolute_path.open("rb") as image_file:
            response = client.post(
                f"/solve/{puzzle}",
                files={"image": (absolute_path.name, image_file, "image/png")},
            )

        if response.status_code != 200:
            print(f"[error] {puzzle}: HTTP {response.status_code}: {response.text[:500]}")
            return 1

        payload = response.json()
        if payload.get("puzzle") != puzzle:
            print(f"[error] {puzzle}: unexpected payload puzzle={payload.get('puzzle')!r}")
            return 1

        print(f"[ok] {puzzle}: solved={payload.get('solved')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
