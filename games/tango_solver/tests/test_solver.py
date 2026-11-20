import json
from pathlib import Path

import pytest

from games.tango_solver.src.tango_solver import TangoSolver
from services.solver_api.app.domain.errors import InvalidBoard
from services.solver_api.app.domain.tango_board import MOON, SUN, tango_solver_input, validate_tango_board
from services.solver_api.app.workers.solve_tango_worker import solve as solve_tango_worker


def test_animation_is_an_injected_output_port() -> None:
    class Recorder:
        def __init__(self):
            self.frames = []
            self.output = None

        def save_frame(self, *args):
            self.frames.append(args[-1])

        def create_gif(self, **kwargs):
            self.output = kwargs
            return kwargs["output_path"]

    recorder = Recorder()
    solver = TangoSolver(visualizer=recorder)
    assert solver.solve(create_gif=True, gif_output="example.gif")
    assert recorder.frames[-1].endswith("SOLVED")
    assert recorder.output["output_path"] == "example.gif"


PAGE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "linkedin-2026-11-20.json"
# LinkedIn's own answer for the 2026-11-20 puzzle (S = sun, M = moon).
OFFICIAL_2026_11_20 = ["SMSSMM", "SMSMMS", "MSMMSS", "MSMSSM", "SMSSMM", "MSMMSS"]


def test_worker_solves_a_page_board_without_the_image() -> None:
    board = json.loads(PAGE_FIXTURE.read_text())
    response = solve_tango_worker(Path("unused.png"), parsed_board=board)

    assert response["solved"], response["error"]
    assert response["details"]["input_source"] == "page"
    assert ["".join("S" if value == SUN else "M" for value in row) for row in response["solution_grid"]] == OFFICIAL_2026_11_20
    assert len(response["moves"]) == 36 - 8
    preset = {(piece["row"], piece["col"]) for piece in response["fixed_pieces"]}
    assert not preset & {(move["row"], move["col"]) for move in response["moves"]}


def test_page_board_maps_suns_moons_and_clues() -> None:
    board = validate_tango_board({"size": 6, "suns": [0], "moons": [7], "equal": [[1, 2]], "opposite": [[2, 8]]})
    fixed, constraints = tango_solver_input(board)
    assert fixed == [(0, 0, SUN), (1, 1, MOON)]
    assert constraints == [("=", (0, 1), (0, 2)), ("x", (0, 2), (1, 2))]


@pytest.mark.parametrize("payload", [
    None, {}, {"size": 6, "suns": [], "moons": [], "equal": []},
    {"size": 8, "suns": [], "moons": [], "equal": [], "opposite": []},
    {"size": 6, "suns": [36], "moons": [], "equal": [], "opposite": []},
    {"size": 6, "suns": [3], "moons": [3], "equal": [], "opposite": []},
    {"size": 6, "suns": [True], "moons": [], "equal": [], "opposite": []},
    {"size": 6, "suns": [], "moons": [], "equal": [[0, 2]], "opposite": []},
    {"size": 6, "suns": [], "moons": [], "equal": [[5, 6]], "opposite": []},
    {"size": 6, "suns": [], "moons": [], "equal": [], "opposite": [[0]]},
    {"size": 6, "suns": [], "moons": [], "equal": [], "opposite": [], "solution": []},
])
def test_invalid_page_boards_are_rejected(payload: object) -> None:
    with pytest.raises(InvalidBoard):
        validate_tango_board(payload)
    if isinstance(payload, dict):
        assert solve_tango_worker(Path("unused.png"), parsed_board=payload)["solved"] is False
