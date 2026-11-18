#!/usr/bin/env python3
"""Prebuild OCR template banks for the bundled fonts into core/assets/ocr_cache.

Hosted instances start with an empty /tmp, so without these files every new
instance renders thousands of glyphs before its first solve. Run this after
changing OCR rendering code, a cache prefix or a bundled font; CI fails while
the shipped files differ from a fresh build.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Module, the lru_cached factory that builds (and disk-caches) its templates,
# and an expression giving the parser's own (writable, packaged) cache paths.
BUILDERS = {
    "sudoku": ("games.sudoku_solver.src.image_parser", "_get_ocr_model", "ocr._dataset_cache_paths()"),
    "patches": ("games.patches_solver.src.image_parser", "_get_ocr", "ocr._classifier_cache_paths()"),
    "wend": ("games.wend_solver.src.image_parser", "_get_ocr",
             "ocr._template_cache_paths(ocr._candidate_font_paths())"),
}


def build_into(game: str, directory: Path) -> tuple[Path, str]:
    """Build one game's cache with the bundled fonts in a fresh process.

    Returns the built file and the file name the parser looks for when packaged.
    """
    module, factory, paths_expression = BUILDERS[game]
    env = {**os.environ, "SOLVER_BUNDLED_FONTS": "1", "TMPDIR": str(directory), "PYTHONPATH": str(REPO_ROOT)}
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[variable] = "1"
    # Hide the packaged copy so the factory really renders the glyphs.
    code = (
        "import core.ocr_fonts as fonts, importlib;"
        "fonts.PACKAGED_OCR_CACHE = fonts.PACKAGED_OCR_CACHE / '__missing__';"
        f"ocr = getattr(importlib.import_module({module!r}), {factory!r})();"
        f"print({paths_expression}[1].name)"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=REPO_ROOT, check=True,
                            capture_output=True, text=True)
    (built,) = directory.glob("*.npz")
    return built, result.stdout.strip().splitlines()[-1]


def pinned_pillow_version() -> str:
    for line in (REPO_ROOT / "services" / "solver_api" / "requirements.txt").read_text().splitlines():
        if line.strip().lower().startswith("pillow=="):
            return line.split("==", 1)[1].strip()
    raise RuntimeError("Pillow is not pinned in services/solver_api/requirements.txt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", nargs="+", choices=sorted(BUILDERS), default=sorted(BUILDERS))
    args = parser.parse_args()

    import PIL

    if PIL.__version__ != pinned_pillow_version():
        # Caches from another Pillow are keyed for that Pillow and never used online.
        print(
            f"[error] Pillow {PIL.__version__} is installed but the API pins {pinned_pillow_version()}. "
            "Run this inside the CI image:\n"
            "  docker build --target ci -f deploy/local/Dockerfile -t solver-ci-env .\n"
            '  docker run --rm --user "$(id -u):$(id -g)" --volume "$PWD:/app" solver-ci-env '
            "python3 scripts/build_ocr_caches.py",
            file=sys.stderr,
        )
        return 1

    from core.ocr_fonts import PACKAGED_OCR_CACHE

    PACKAGED_OCR_CACHE.mkdir(parents=True, exist_ok=True)
    for game in args.games:
        with tempfile.TemporaryDirectory(prefix=f"ocr_cache_{game}_") as tmp:
            built, name = build_into(game, Path(tmp))
            prefix = name.rsplit("_", 1)[0]
            for stale in PACKAGED_OCR_CACHE.glob(f"{prefix}_*.npz"):
                stale.unlink()
            shutil.copyfile(built, PACKAGED_OCR_CACHE / name)
            print(f"[ok] {game}: core/assets/ocr_cache/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
