#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
import os
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.bootstrap import create_app
from services.solver_api.app.puzzle_registry import PUZZLE_DEFINITIONS


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve all tracked samples through the local or deployed API.")
    parser.add_argument("--base-url", help="HTTPS API URL; omit to exercise the ASGI application locally.")
    parser.add_argument("--hosted", action="store_true", help="Exercise the Vercel profile and bundled OCR fonts locally.")
    args = parser.parse_args()
    if args.hosted:
        os.environ["VERCEL"] = "1"
        for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            os.environ[variable] = "1"
    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120) if args.base_url else TestClient(create_app())

    for path in ("/", "/privacy", "/support"):
        response = client.get(path)
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            print(f"[error] {path}: expected HTML page, got HTTP {response.status_code}")
            return 1
        print(f"[ok] {path}: public HTML page", flush=True)

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

        # Solve from the image alone and, when a page board is recorded, from that too.
        inputs = [("image", None)] if definition.image_input else []
        if definition.page_board_fixture:
            inputs.append(("with page board", (REPO_ROOT / definition.page_board_fixture).read_text(encoding="utf-8")))
        for source, page_board in inputs:
            start = time.perf_counter()
            with absolute_path.open("rb") as image_file:
                response = client.post(
                    f"/solve/{puzzle}",
                    files={"image": (absolute_path.name, image_file, "image/png")},
                    data={"parsed_board": page_board} if page_board is not None else None,
                )

            if response.status_code != 200:
                print(f"[error] {puzzle} ({source}): HTTP {response.status_code}: {response.text[:500]}")
                return 1

            payload = response.json()
            if payload.get("puzzle") != puzzle:
                print(f"[error] {puzzle} ({source}): unexpected payload puzzle={payload.get('puzzle')!r}")
                return 1
            if not payload.get("solved"):
                print(f"[error] {puzzle} ({source}): sample was not solved: {payload.get('error')}")
                return 1

            elapsed = time.perf_counter() - start
            print(f"[ok] {puzzle} ({source}): solved={payload.get('solved')} elapsed={elapsed:.2f}s", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
