from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(params=("sample1.png", "sample6.png"))
def image_path(request: pytest.FixtureRequest) -> str:
    sample_path = Path(__file__).resolve().parents[1] / "examples" / str(request.param)
    assert sample_path.is_file(), f"Missing tracked Tango sample: {sample_path}"
    return str(sample_path)
