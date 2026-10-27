from scripts.check_architecture import check, violations


def test_inner_layers_are_independent_of_adapters() -> None:
    assert check() == []


def test_guard_rejects_relative_adapter_and_framework_imports() -> None:
    path = "services/solver_api/app/application/use_case.py"
    assert violations("from ..adapters.memory import MemorySolutionCache", path)
    assert violations("from fastapi import HTTPException", path)
    assert violations("from .. import bootstrap", path)
    assert not violations("from ..domain.models import SolveRequest", path)
    assert violations("from .visualizer import BoardVisualizer", "games/tango_solver/src/tango_solver.py")
