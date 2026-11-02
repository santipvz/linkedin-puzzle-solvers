from __future__ import annotations

import subprocess
import json
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
from services.solver_api.app.domain.errors import EmptyImage, ImageTooLarge, InvalidBoard, SolverTimeout, UnknownPuzzle, UnsupportedImage, WorkerFailure
from services.solver_api.app.domain.models import SolveRequest


class FakeSolver:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def solve(self, puzzle, image, filename, *, parsed_board=None):
        self.calls.append((puzzle, image, filename, parsed_board))
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


def page_board():
    path = Path(__file__).resolve().parents[3] / "games/wend_solver/tests/fixtures/linkedin-2026-10-29.json"
    return json.loads(path.read_text())


def test_page_board_is_validated_and_has_a_separate_cache_entry():
    use_case, solver, _ = service()
    request = SolveRequest("wend", b"image", parsed_board=page_board())
    use_case.execute(request)
    use_case.execute(request)
    assert len(solver.calls) == 1
    assert solver.calls[0][-1] == page_board()
    use_case.execute(replace(request, parsed_board=None))
    assert len(solver.calls) == 2
    changed = page_board()
    changed["board"][0][0] = "A"
    use_case.execute(replace(request, parsed_board=changed))
    assert len(solver.calls) == 3


@pytest.mark.parametrize("payload", [
    {}, {"board": [["A"]], "lengths": [1]},
    {"board": [["A"] * 5] * 5, "lengths": [True, 8, 16]},
    {"board": [["A"] * 5] * 5, "lengths": [3]},
    {"board": [["?"] * 5] * 5, "lengths": [9, 16]},
    {"board": [["é"] * 5] * 5, "lengths": [9, 16]},
])
def test_malformed_page_boards_never_reach_the_worker(payload):
    use_case, solver, _ = service()
    with pytest.raises(InvalidBoard):
        use_case.execute(SolveRequest("wend", b"image", parsed_board=payload))
    assert not solver.calls


def test_http_page_board_round_trip_and_validation():
    use_case, solver, _ = service()
    use_case.cache_revisions["zip"] = 1
    client = TestClient(create_http_app(use_case, ["wend", "zip"]))
    image = {"image": ("board.png", b"image", "image/png")}
    response = client.post("/solve/wend", files=image, data={"parsed_board": json.dumps(page_board())})
    assert response.status_code == 200
    assert solver.calls[-1][-1] == page_board()
    for payload in ["{", "null", "[]", "{}", " " * 4097]:
        assert client.post("/solve/wend", files=image, data={"parsed_board": payload}).status_code == 422
    assert client.post("/solve/zip", files=image, data={"parsed_board": json.dumps(page_board())}).status_code == 422


@pytest.mark.parametrize("mode", ["subprocess", "inprocess"])
def test_page_board_reaches_the_real_worker(mode):
    root = Path(__file__).resolve().parents[3]
    worker = WorkerSolver({"wend": "solve_wend_worker.py"}, root / "services/solver_api/app/workers", mode=mode)
    result = worker.solve("wend", b"unused image", "board.png", parsed_board=page_board())
    assert result["solved"]
    assert result["details"]["input_source"] == "page"
    assert {word["word"] for word in result["words"]} == {"OAR", "FLOOR", "MIRROR", "OREGANO", "FOOTWORK"}
