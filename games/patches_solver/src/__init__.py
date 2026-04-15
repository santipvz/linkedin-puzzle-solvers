from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .image_parser import PatchesImageParser
    from .patches_solver import PatchesClue, PatchesRegion, PatchesSolveResult, PatchesSolver

__all__ = [
    "PatchesClue",
    "PatchesImageParser",
    "PatchesRegion",
    "PatchesSolveResult",
    "PatchesSolver",
]

_EXPORT_MAP = {
    "PatchesClue": ".patches_solver",
    "PatchesImageParser": ".image_parser",
    "PatchesRegion": ".patches_solver",
    "PatchesSolveResult": ".patches_solver",
    "PatchesSolver": ".patches_solver",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
