from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .image_parser import MiniSudokuImageParser
    from .mini_sudoku_solver import MiniSudokuSolveResult, MiniSudokuSolver

__all__ = [
    "MiniSudokuImageParser",
    "MiniSudokuSolver",
    "MiniSudokuSolveResult",
]

_EXPORT_MAP = {
    "MiniSudokuImageParser": ".image_parser",
    "MiniSudokuSolver": ".mini_sudoku_solver",
    "MiniSudokuSolveResult": ".mini_sudoku_solver",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
