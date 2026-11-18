from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from services.solver_api.app.adapters.http import create_http_app
from services.solver_api.app.adapters.memory import MemorySolutionCache
from services.solver_api.app.adapters.workers import WorkerSolver
from services.solver_api.app.application.solve_puzzle import SolvePuzzle
from services.solver_api.app.domain.errors import SolverBusy, SolverTimeout, WorkerFailure
from services.solver_api.app.puzzle_registry import PUZZLE_DEFINITIONS
from services.solver_api.app.settings import REPO_ROOT


@pytest.fixture
def worker(tmp_path):
    source = '''
import os
import time
count = 0
def solve(image_path, *, parsed_board=None):
    global count
    data = image_path.read_bytes()
    if data == b"timeout": time.sleep(10)
    if data == b"crash": os._exit(1)
    if data == b"error": raise ValueError("bad board")
    count += 1
    print("solver diagnostics must not break transport")
    return {"count": count, "pid": os.getpid(), "board": parsed_board, "image": data.decode()}
'''
    for filename in ("one.py", "two.py", "three.py"):
        (tmp_path / filename).write_text(source)
    solver = WorkerSolver({"one": "one.py", "two": "two.py", "three": "three.py"}, tmp_path, mode="persistent", timeout=1,
                          max_warm_workers=2)
    try:
        yield solver
    finally:
        solver.close()


def child(worker, name):
    entry = worker._persistent.children.get(worker.workers_directory / f"{name}.py")
    return None if entry is None else entry


def process(worker, name):
    entry = child(worker, name)
    return None if entry is None else entry.process


def test_keeps_one_warm_child_per_game_and_evicts_the_least_recent(worker):
    first = worker.solve("one", b"first", None)
    board = {"letters": ["A"]}
    second = worker.solve("one", b"second", None, parsed_board=board)
    assert second == {"count": 2, "pid": first["pid"], "board": board, "image": "second"}
    one = process(worker, "one")
    other = worker.solve("two", b"other", None)
    assert other["count"] == 1 and other["pid"] != first["pid"]
    # Switching back reuses the warm child instead of starting a new one.
    assert worker.solve("one", b"again", None) == {"count": 3, "pid": first["pid"], "board": None, "image": "again"}
    two = process(worker, "two")
    worker.solve("three", b"third", None)
    assert two.poll() is not None
    assert one.poll() is None
    assert child(worker, "two") is None
    worker.close()
    assert one.poll() is not None
    assert worker._persistent.children == {}


@pytest.mark.parametrize("payload,error", [(b"timeout", SolverTimeout), (b"crash", WorkerFailure), (b"error", WorkerFailure)])
def test_failures_kill_child_remove_upload_and_allow_next_request(worker, payload, error):
    paths = []
    write = worker._write_temp_image

    def track(*args):
        path = write(*args)
        paths.append(path)
        return path

    worker._write_temp_image = track
    with pytest.raises(error):
        worker.solve("one", payload, None)
    assert process(worker, "one") is None
    assert not paths[-1].exists()
    assert worker.solve("one", b"recovered", None)["count"] == 1
    assert not paths[-1].exists()


def test_overlapping_requests_do_not_mix_transport_messages(worker):
    worker.solve("one", b"warm", None)
    with child(worker, "one").lock:
        with pytest.raises(SolverBusy):
            worker.solve("one", b"image", None)
    assert worker.solve("one", b"image", None)["count"] == 2


def test_busy_children_are_not_evicted(worker):
    worker.solve("one", b"warm", None)
    worker.solve("two", b"warm", None)
    one = process(worker, "one")
    with child(worker, "one").lock:
        worker.solve("three", b"third", None)
    assert one.poll() is None
    assert child(worker, "two") is None


def test_http_shutdown_reaps_the_persistent_child(worker):
    service = SolvePuzzle(worker, MemorySolutionCache(), Mock(), {"one": 1})
    with TestClient(create_http_app(service, ("one",))) as client:
        response = client.post("/solve/one", files={"image": ("board.png", b"image", "image/png")})
        assert response.status_code == 200
        running = process(worker, "one")
        assert running.poll() is None
    assert running.poll() is not None
    assert worker._persistent.children == {}


@pytest.mark.parametrize("puzzle", PUZZLE_DEFINITIONS, ids=lambda p: p.key)
def test_repeated_real_solves_match_isolated_workers(puzzle, monkeypatch):
    monkeypatch.setenv("SOLVER_BUNDLED_FONTS", "1")
    for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        monkeypatch.setenv(variable, "1")
    directory = REPO_ROOT / "services/solver_api/app/workers"
    files = {puzzle.key: puzzle.worker_filename}
    worker = WorkerSolver(files, directory, mode="persistent")
    isolated = WorkerSolver(files, directory)
    image = (REPO_ROOT / puzzle.sample_image).read_bytes()
    board = json.loads((REPO_ROOT / puzzle.page_board_fixture).read_text()) if puzzle.page_board_fixture else None
    try:
        expected = isolated.solve(puzzle.key, image, "board.png", parsed_board=board)
        assert expected["solved"]
        def stable(value):
            if isinstance(value, dict):
                return {key: stable(item) for key, item in value.items() if key not in {"logs", "execution_time_sec"}}
            if isinstance(value, list):
                return [stable(item) for item in value]
            return value

        for _ in range(2):
            result = worker.solve(puzzle.key, image, "board.png", parsed_board=board)
            assert stable(result) == stable(expected)
    finally:
        worker.close()


def test_persistent_wend_supports_page_input():
    board = json.loads((REPO_ROOT / "games/wend_solver/tests/fixtures/linkedin-2026-10-29.json").read_text())
    solver = WorkerSolver({"wend": "solve_wend_worker.py"}, REPO_ROOT / "services/solver_api/app/workers", mode="persistent")
    try:
        for _ in range(2):
            result = solver.solve("wend", b"unused", None, parsed_board=board)
            assert result["solved"]
            assert result["details"]["input_source"] == "page"
    finally:
        solver.close()
