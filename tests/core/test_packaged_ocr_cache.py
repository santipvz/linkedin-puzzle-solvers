from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from core.ocr_fonts import BUNDLED_FONTS, PACKAGED_OCR_CACHE, packaged_ocr_cache_path


REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("build_ocr_caches", REPO_ROOT / "scripts" / "build_ocr_caches.py")
build_ocr_caches = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_ocr_caches)


@pytest.mark.parametrize("game", sorted(build_ocr_caches.BUILDERS))
def test_packaged_cache_matches_a_fresh_build(game, tmp_path):
    built, name = build_ocr_caches.build_into(game, tmp_path)
    packaged = PACKAGED_OCR_CACHE / name
    assert packaged.exists(), f"Run python3 scripts/build_ocr_caches.py --games {game}"
    with np.load(built) as fresh, np.load(packaged) as shipped:
        assert sorted(fresh.files) == sorted(shipped.files)
        for key in fresh.files:
            np.testing.assert_array_equal(fresh[key], shipped[key], err_msg=f"{game}: stale {key}; rebuild the OCR cache")


def test_packaged_caches_have_no_orphans():
    names = {path.name for path in PACKAGED_OCR_CACHE.glob("*.npz")}
    prefixes = [name.rsplit("_", 1)[0] for name in names]
    assert len(prefixes) == len(set(prefixes)) == len(build_ocr_caches.BUILDERS)


def test_packaged_path_depends_on_font_content_not_location(tmp_path):
    font = BUNDLED_FONTS / "DejaVuSans.ttf"
    assert packaged_ocr_cache_path("prefix", [str(font)]) is not None
    copy = tmp_path / font.name
    copy.write_bytes(font.read_bytes())
    # Fonts outside the bundled directory are system fonts: no packaged cache.
    assert packaged_ocr_cache_path("prefix", [str(copy)]) is None
    assert packaged_ocr_cache_path("prefix", []) is None
