from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PuzzleDefinition:
    key: str
    worker_filename: str
    sample_image: str
    expected_board_size: int
    sample_required: bool = True

    @property
    def endpoint_path(self) -> str:
        return f"/solve/{self.key}"


PUZZLE_DEFINITIONS: tuple[PuzzleDefinition, ...] = (
    PuzzleDefinition(
        key="queens",
        worker_filename="solve_queens_worker.py",
        sample_image="games/queen_solver/examples/sample1.png",
        expected_board_size=9,
        sample_required=True,
    ),
    PuzzleDefinition(
        key="tango",
        worker_filename="solve_tango_worker.py",
        sample_image="games/tango_solver/examples/sample1.png",
        expected_board_size=6,
        sample_required=True,
    ),
    PuzzleDefinition(
        key="sudoku",
        worker_filename="solve_sudoku_worker.py",
        sample_image="games/sudoku_solver/examples/sample1.png",
        expected_board_size=6,
        sample_required=False,
    ),
    PuzzleDefinition(
        key="zip",
        worker_filename="solve_zip_worker.py",
        sample_image="games/zip_solver/examples/sample1.png",
        expected_board_size=7,
        sample_required=False,
    ),
    PuzzleDefinition(
        key="patches",
        worker_filename="solve_patches_worker.py",
        sample_image="games/patches_solver/examples/sample1.png",
        expected_board_size=6,
        sample_required=False,
    ),
)


PUZZLES_BY_KEY: dict[str, PuzzleDefinition] = {definition.key: definition for definition in PUZZLE_DEFINITIONS}


def get_puzzle_definition(key: str) -> PuzzleDefinition:
    definition = PUZZLES_BY_KEY.get(key)
    if definition is None:
        raise KeyError(f"Unknown puzzle: {key}")
    return definition
