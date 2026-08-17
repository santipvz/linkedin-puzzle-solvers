from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from games.wend_solver.src.image_parser import WendImageParser


def benchmark(dataset_root: Path) -> int:
    parser = WendImageParser()
    checked = 0
    failed = 0
    for metadata_path in sorted(dataset_root.rglob("*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        artifact_filename = metadata.get("artifact_filename")
        if isinstance(artifact_filename, str) and artifact_filename:
            image_path = metadata_path.parent / artifact_filename
        else:
            candidates = [
                path
                for path in metadata_path.parent.glob(f"{metadata_path.stem}.*")
                if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".img"}
            ]
            image_path = candidates[0] if candidates else metadata_path.with_suffix(".png")
        if not image_path.is_file():
            continue
        details = metadata.get("details") if isinstance(metadata.get("details"), dict) else {}
        if not metadata.get("solved") or details.get("parse_reliable") is not True:
            continue
        expected_size = int(metadata.get("board_size") or 0)
        expected_visible = int(details.get("visible_cells") or 0)
        if expected_size <= 0 or expected_visible <= 0:
            continue
        parsed = parser.parse_image(image_path)
        checked += 1
        if parsed["board_size"] != expected_size or parsed["visible_cells"] != expected_visible:
            failed += 1
            print(
                f"[fail] {image_path}: expected {expected_size}/{expected_visible}, "
                f"got {parsed['board_size']}/{parsed['visible_cells']}"
            )

    print(f"Wend dataset benchmark: {checked - failed}/{checked} captures matched")
    return 1 if failed or checked == 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Wend board parsing against archived metadata.")
    parser.add_argument("dataset", nargs="?", type=Path, default=REPO_ROOT / "datasets" / "wend")
    args = parser.parse_args()
    return benchmark(args.dataset)


if __name__ == "__main__":
    raise SystemExit(main())
