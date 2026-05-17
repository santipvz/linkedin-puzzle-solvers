from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .constraint_classifier import ConstraintClassifier
    from .grid_detector import GridDetector
    from .image_parser import TangoImageParser
    from .piece_detector import PieceDetector
    from .tango_solver import TangoSolver
    from .template_constraint_classifier import TemplateConstraintClassifier
    from .visualizer import BoardVisualizer

__all__ = [
    "GridDetector",
    "PieceDetector",
    "TangoImageParser",
    "ConstraintClassifier",
    "TemplateConstraintClassifier",
    "TangoSolver",
    "BoardVisualizer",
]

_EXPORT_MAP = {
    "GridDetector": ".grid_detector",
    "PieceDetector": ".piece_detector",
    "TangoImageParser": ".image_parser",
    "ConstraintClassifier": ".constraint_classifier",
    "TemplateConstraintClassifier": ".template_constraint_classifier",
    "TangoSolver": ".tango_solver",
    "BoardVisualizer": ".visualizer",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


__version__ = "1.0.0"
