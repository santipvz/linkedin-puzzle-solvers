from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def image_path() -> str:
    sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample1.png"
    if not sample_path.exists():
        pytest.skip(f"Missing tango sample image: {sample_path}")
    return str(sample_path)
