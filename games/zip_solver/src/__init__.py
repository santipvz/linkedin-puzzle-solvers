from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .image_parser import ZipImageParser
    from .zip_solver import ZipSolveResult, ZipSolver

__all__ = [
    "ZipImageParser",
    "ZipSolveResult",
    "ZipSolver",
]

_EXPORT_MAP = {
    "ZipImageParser": ".image_parser",
    "ZipSolveResult": ".zip_solver",
    "ZipSolver": ".zip_solver",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
