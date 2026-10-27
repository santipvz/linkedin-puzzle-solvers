from __future__ import annotations

import os
import tomllib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.ocr_fonts import BUNDLED_FONTS, ocr_font_paths
from services.solver_api.app.adapters.workers import WorkerSolver
from services.solver_api.app.bootstrap import create_app
from services.solver_api.app.domain.errors import SolverBusy, WorkerFailure
from services.solver_api.app.settings import Settings
from services.solver_api.app.settings import REPO_ROOT


def test_vercel_and_docker_install_the_same_runtime_dependencies():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    docker = (REPO_ROOT / "services/solver_api/requirements.txt").read_text().splitlines()
    assert sorted(project["project"]["dependencies"]) == sorted(line for line in docker if line.strip())


def test_serverless_defaults_keep_uploads_below_platform_limit_and_disable_archiving():
    with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
        settings = Settings.from_env()
    assert not settings.capture_enabled
    assert settings.max_upload_bytes == 4 * 1024 * 1024
    assert settings.max_concurrent_workers == 1
    with patch.dict(os.environ, {}, clear=True):
        local = Settings.from_env()
    assert local.capture_enabled
    assert local.max_upload_bytes == 10 * 1024 * 1024
    assert local.max_concurrent_workers == 0


def test_fonts_work_without_system_fonts_and_hosted_ocr_is_deterministic(tmp_path):
    local_font = tmp_path / "Local.ttf"
    local_font.touch()
    patterns = (str(local_font),)
    with patch.dict(os.environ, {}, clear=True):
        assert ocr_font_paths(patterns, ("DejaVuSans.ttf",)) == [str(local_font)]
        assert ocr_font_paths(("/missing/*.ttf",), ("DejaVuSans.ttf",)) == [str(BUNDLED_FONTS / "DejaVuSans.ttf")]
    with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
        assert ocr_font_paths(patterns, ("DejaVuSans.ttf",)) == [str(BUNDLED_FONTS / "DejaVuSans.ttf")]


def test_worker_capacity_is_released_after_tempfile_or_worker_failure(tmp_path):
    worker = WorkerSolver({"wend": "worker.py"}, tmp_path, max_concurrent_workers=1)
    with patch.object(worker, "_write_temp_image", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            worker.solve("wend", b"image", "board.png")
    with patch.object(worker, "_run_solver_worker", side_effect=WorkerFailure("failed")):
        with pytest.raises(WorkerFailure):
            worker.solve("wend", b"image", "board.png")
    with patch.object(worker, "_run_solver_worker", return_value={"solved": True}):
        assert worker.solve("wend", b"image", "board.png")["solved"]
    assert worker._slots.acquire(blocking=False)
    try:
        with pytest.raises(SolverBusy):
            worker.solve("wend", b"image", "board.png")
    finally:
        worker._slots.release()


def test_busy_worker_returns_retryable_http_response():
    client = TestClient(create_app(Settings(capture_enabled=False, max_concurrent_workers=1)))
    with patch.object(WorkerSolver, "solve", side_effect=SolverBusy("Busy")):
        response = client.post("/solve/wend", files={"image": ("board.png", b"image", "image/png")})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
