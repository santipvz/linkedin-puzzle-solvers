from __future__ import annotations

from games.tango_solver.src.image_parser import TangoImageParser
from games.tango_solver.src.tango_solver import TangoSolver


def test_sample_parser_contract_and_solver(image_path: str) -> None:
    board_state = TangoImageParser().parse_image(image_path)

    assert board_state is not None
    fixed_pieces = board_state["fixed_pieces"]
    empty_cells = board_state["empty_cells"]
    constraints = board_state["constraints"]
    positions = {(piece["row"], piece["col"]) for piece in fixed_pieces}
    positions.update(tuple(position) for position in empty_cells)
    assert len(fixed_pieces) + len(empty_cells) == 36
    assert len(positions) == 36
    assert fixed_pieces or constraints
    assert all(piece["piece_type"] in (0, 1) for piece in fixed_pieces)
    assert all(0 <= piece["row"] < 6 and 0 <= piece["col"] < 6 for piece in fixed_pieces)

    for constraint in constraints:
        assert constraint["type"] in ("=", "x")
        row_delta = abs(constraint["pos1"][0] - constraint["pos2"][0])
        col_delta = abs(constraint["pos1"][1] - constraint["pos2"][1])
        assert row_delta + col_delta == 1

    solver = TangoSolver()
    for piece in fixed_pieces:
        solver.add_fixed_piece(piece["row"], piece["col"], piece["piece_type"])
    for constraint in constraints:
        solver.add_constraint(constraint["type"], constraint["pos1"], constraint["pos2"])
    assert solver.solve()


def test_missing_image_returns_none() -> None:
    assert TangoImageParser().parse_image("missing-tango-image.png") is None


def test_current_small_antialiased_constraint_signs() -> None:
    from pathlib import Path
    from services.solver_api.app.workers.solve_tango_worker import solve

    image = Path(__file__).parent / "fixtures" / "linkedin-2026-10-28.jpg"
    result = solve(image)
    assert result["solved"], result.get("error")
    assert result["details"]["fixed_count"] == 6
    assert result["constraints"] == [
        {"type": "=", "pos1": [1, 2], "pos2": [2, 2]},
        {"type": "x", "pos1": [3, 4], "pos2": [4, 4]},
        {"type": "=", "pos1": [3, 5], "pos2": [4, 5]},
    ]
    assert len(result["moves"]) == 30
