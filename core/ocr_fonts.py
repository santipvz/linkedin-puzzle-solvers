"""Portable OCR fonts, with system fonts retained for existing local setups."""
from __future__ import annotations

import glob
import hashlib
import os
from pathlib import Path
from collections.abc import Sequence


BUNDLED_FONTS = Path(__file__).parent / "assets" / "fonts"


def ocr_font_paths(system_patterns: Sequence[str], bundled_patterns: Sequence[str]) -> list[str]:
    bundled = [str(path) for pattern in bundled_patterns for path in sorted(BUNDLED_FONTS.glob(pattern))]
    if os.getenv("SOLVER_BUNDLED_FONTS", os.getenv("VERCEL", "0")) == "1":
        return list(dict.fromkeys(bundled))
    system = [path for pattern in system_patterns for path in sorted(glob.glob(pattern)) if Path(path).is_file()]
    return list(dict.fromkeys(system or bundled))


def font_fingerprint(paths: Sequence[str]) -> str:
    signatures = [f"{path}:{Path(path).stat().st_size}:{Path(path).stat().st_mtime_ns}" for path in paths]
    return hashlib.sha256("\n".join(signatures).encode()).hexdigest()[:16]
