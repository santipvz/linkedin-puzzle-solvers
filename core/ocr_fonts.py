"""Portable OCR fonts, with system fonts retained for existing local setups."""
from __future__ import annotations

import glob
import hashlib
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from collections.abc import Sequence


BUNDLED_FONTS = Path(__file__).parent / "assets" / "fonts"
# OCR template banks prebuilt from BUNDLED_FONTS (scripts/build_ocr_caches.py).
# New hosted instances load these instead of rendering thousands of glyphs.
PACKAGED_OCR_CACHE = Path(__file__).parent / "assets" / "ocr_cache"


def ocr_font_paths(system_patterns: Sequence[str], bundled_patterns: Sequence[str]) -> list[str]:
    bundled = [str(path) for pattern in bundled_patterns for path in sorted(BUNDLED_FONTS.glob(pattern))]
    if os.getenv("SOLVER_BUNDLED_FONTS", os.getenv("VERCEL", "0")) == "1":
        return list(dict.fromkeys(bundled))
    system = [path for pattern in system_patterns for path in sorted(glob.glob(pattern)) if Path(path).is_file()]
    return list(dict.fromkeys(system or bundled))


def font_fingerprint(paths: Sequence[str]) -> str:
    signatures = [f"{path}:{Path(path).stat().st_size}:{Path(path).stat().st_mtime_ns}" for path in paths]
    return hashlib.sha256("\n".join(signatures).encode()).hexdigest()[:16]


def rasterizer_signature() -> str:
    """Pillow and FreeType versions: glyph pixels can differ between them."""
    try:
        import PIL
        from PIL import features

        freetype = features.version("freetype2") or "none"
        return f"pillow-{PIL.__version__}-freetype-{freetype}"
    except Exception:
        return "unknown"


@lru_cache(maxsize=32)
def _bundled_content_fingerprint(paths: tuple[str, ...]) -> str | None:
    bundled_root = BUNDLED_FONTS.resolve()
    digest = hashlib.sha256()
    # Prebuilt templates are only valid where glyphs rasterize identically.
    digest.update(rasterizer_signature().encode())
    for path in paths:
        resolved = Path(path).resolve()
        if resolved.parent != bundled_root:
            return None
        digest.update(resolved.name.encode())
        digest.update(hashlib.sha256(resolved.read_bytes()).digest())
    return digest.hexdigest()[:16]


def packaged_ocr_cache_path(prefix: str, paths: Sequence[str]) -> Path | None:
    """Prebuilt cache for ``paths`` when they are all bundled fonts.

    Keyed by font names and contents plus the Pillow/FreeType versions, not by
    install path or modification time, so it matches on any machine that ships
    the same fonts and renders them with the same pinned Pillow (CI, Docker
    and Vercel). Other setups rebuild the templates as before.
    """
    if not paths:
        return None
    fingerprint = _bundled_content_fingerprint(tuple(paths))
    return None if fingerprint is None else PACKAGED_OCR_CACHE / f"{prefix}_{fingerprint}.npz"


def ocr_cache_paths(prefix: str, paths: Sequence[str]) -> tuple[Path, Path | None]:
    """The writable per-machine cache path, and the read-only packaged one if any."""
    writable = Path(tempfile.gettempdir()) / f"{prefix}_{font_fingerprint(paths)}.npz"
    return writable, packaged_ocr_cache_path(prefix, paths)
