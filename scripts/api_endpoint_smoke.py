#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.main import app
from services.solver_api.app.puzzle_registry import PUZZLE_DEFINITIONS


def main() -> int:
    client = TestClient(app)

    for definition in PUZZLE_DEFINITIONS:
        puzzle = definition.key
        sample_path = definition.sample_image
        absolute_path = REPO_ROOT / sample_path
        if not absolute_path.exists():
            if definition.sample_required:
                print(f"[error] {puzzle}: missing required sample {sample_path}")
                return 1
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
        if not payload.get("solved"):
            print(f"[error] {puzzle}: sample was not solved: {payload.get('error')}")
            return 1

        print(f"[ok] {puzzle}: solved={payload.get('solved')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
