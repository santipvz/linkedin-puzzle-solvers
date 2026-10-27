from __future__ import annotations

import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.solver_api.app.adapters.captures import FileCaptureStore
from services.solver_api.app.adapters.http import create_http_app
from services.solver_api.app.adapters.memory import MemorySolutionCache
from services.solver_api.app.adapters.workers import WorkerSolver
from services.solver_api.app.application.solve_puzzle import SolvePuzzle
from services.solver_api.app.domain.errors import EmptyImage, ImageTooLarge, SolverTimeout, UnknownPuzzle, UnsupportedImage, WorkerFailure
from services.solver_api.app.domain.models import SolveRequest


class FakeSolver:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def solve(self, puzzle, image, filename):
        self.calls.append((puzzle, image, filename))
        if self.error:
            raise self.error
        return {"puzzle": puzzle, "solved": True, "details": {"parse_reliable": True}}


class FakeCaptures:
    def __init__(self):
        self.calls = []

    def save(self, *args):
        self.calls.append(args)


def service(error=None):
    solver, captures = FakeSolver(error), FakeCaptures()
    use_case = SolvePuzzle(solver, MemorySolutionCache(2), captures, {"wend": 4}, max_upload_bytes=8)
    return use_case, solver, captures


def test_solve_and_capture_work_without_http_files_or_real_workers() -> None:
    use_case, solver, captures = service()
    request = SolveRequest("wend", b"image", "board.png", "image/png", capture=True)
    first = use_case.execute(request)
    first["solved"] = False  # callers must not mutate the cached response
    assert use_case.execute(request)["solved"] is True
    assert len(solver.calls) == 1
    assert [call[-1] for call in captures.calls] == [False, True]
    assert all(call[1] == b"image" for call in captures.calls)
    use_case.cache_revisions["wend"] = 5
    use_case.execute(request)
    assert len(solver.calls) == 2


@pytest.mark.parametrize(("changes", "error"), [
    ({"image": b""}, EmptyImage),
    ({"image": b"too large"}, ImageTooLarge),
    ({"content_type": "text/plain"}, UnsupportedImage),
    ({"puzzle": "unknown"}, UnknownPuzzle),
])
def test_validation_prevents_outbound_effects(changes, error) -> None:
    use_case, solver, captures = service()
    with pytest.raises(error):
        use_case.execute(replace(SolveRequest("wend", b"image"), **changes))
    assert solver.calls == []
    assert captures.calls == []


def test_lru_eviction_and_reads_are_isolated() -> None:
    cache = MemorySolutionCache(2)
    cache.put("a", {"value": 1})
    cache.put("b", {"value": 2})
    cached = cache.get("a")
    cached["value"] = 99
    cache.put("c", {"value": 3})
    assert cache.get("b") is None
    assert cache.get("a") == {"value": 1}


@pytest.mark.parametrize(("error", "status"), [(SolverTimeout("late"), 504), (WorkerFailure("broken"), 500)])
def test_http_translates_application_errors(error, status) -> None:
    use_case, _, _ = service(error)
    client = TestClient(create_http_app(use_case, ["wend"]))
    result = client.post("/solve/wend", files={"image": ("board.png", b"image", "image/png")})
    assert result.status_code == status
    assert result.json() == {"detail": str(error)}


def test_http_preserves_upload_validation_and_start_capture_contract() -> None:
    use_case, solver, captures = service()
    client = TestClient(create_http_app(use_case, ["wend"]))
    assert client.get("/health").json() == {"status": "ok"}
    for image, content_type, status in [(b"", "image/png", 400), (b"too large", "image/png", 413), (b"image", "text/plain", 415)]:
        response = client.post("/solve/wend", files={"image": ("board.png", image, content_type)})
        assert response.status_code == status
    assert solver.calls == []
    assert client.post("/solve/wend", files={"image": ("board.png", b"image", "image/png")}).status_code == 200
    assert captures.calls == []
    response = client.post("/solve/wend", headers={"X-Board-Capture": "start"},
                           files={"image": ("board.png", b"image", "image/png")})
    assert response.status_code == 200
    assert captures.calls[-1][-1] is True


def test_worker_timeout_cleans_up_image_and_does_not_cache_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        worker_file = Path(tmp) / "worker.py"
        worker_file.write_text("")
        worker = WorkerSolver({"wend": "worker.py"}, Path(tmp), timeout=1)
        image_paths = []

        def timeout(command, **kwargs):
            image_paths.append(Path(command[-1]))
            assert image_paths[-1].read_bytes() == b"image"
            raise subprocess.TimeoutExpired(command, 1)

        with patch("services.solver_api.app.adapters.workers.subprocess.run", side_effect=timeout):
            use_case = SolvePuzzle(worker, MemorySolutionCache(), FakeCaptures(), {"wend": 4})
            for _ in range(2):
                with pytest.raises(SolverTimeout):
                    use_case.execute(SolveRequest("wend", b"image"))
        assert len(image_paths) == 2
        assert all(not path.exists() for path in image_paths)


def test_capture_failure_does_not_fail_a_solve(caplog) -> None:
    use_case, _, _ = service()
    use_case.captures = FileCaptureStore(Path("unused"), Path("."))
    with patch.object(use_case.captures, "_archive_board_capture", side_effect=PermissionError("read-only")):
        assert use_case.execute(SolveRequest("wend", b"image", capture=True))["solved"]
    assert "read-only" in caplog.text
