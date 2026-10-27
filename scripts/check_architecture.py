"""Enforce inward dependencies without importing the application or its adapters."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP = "services.solver_api.app"
PURE_SOLVERS = (
    "games/patches_solver/src/patches_solver.py",
    "games/sudoku_solver/src/mini_sudoku_solver.py",
    "games/zip_solver/src/zip_solver.py",
    "games/wend_solver/src/wend_solver.py",
    "games/tango_solver/src/tango_solver.py",
    "games/tango_solver/src/ports.py",
    "games/queen_solver/src/core/models.py",
    "games/queen_solver/src/core/interfaces.py",
    "games/queen_solver/src/solver/queens_solver.py",
    "games/queen_solver/src/solver/validator.py",
)


def violations(source: str, relative_path: str) -> list[str]:
    path = Path(relative_path)
    package = list(path.parent.parts)
    if relative_path.startswith("services/solver_api/app/domain/"):
        allowed = (f"{APP}.domain",)
    elif relative_path.startswith("services/solver_api/app/application/"):
        allowed = (f"{APP}.domain", f"{APP}.application")
    else:
        allowed = (
            "numpy", "src.core", "src.solver", "games.queen_solver.src.core",
            "games.queen_solver.src.solver", "games.tango_solver.src.ports",
        )
    errors = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[:len(package) - node.level + 1] if node.level else []
            module = ".".join(base + ([node.module] if node.module else []))
            modules = [module] if node.module else [f"{module}.{alias.name}" for alias in node.names]
        else:
            continue
        for module in modules:
            if module.split(".")[0] in sys.stdlib_module_names:
                continue
            if not any(module == prefix or module.startswith(prefix + ".") for prefix in allowed):
                errors.append(f"{relative_path}:{node.lineno}: forbidden inner-layer dependency: {module}")
    return errors


def check(root: Path = REPO_ROOT) -> list[str]:
    paths = [root / path for path in PURE_SOLVERS]
    for layer in ("domain", "application"):
        paths.extend((root / "services/solver_api/app" / layer).rglob("*.py"))
    return [error for path in paths for error in violations(path.read_text(), path.relative_to(root).as_posix())]


if __name__ == "__main__":
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("[ok] domain and application dependencies point inward")
    raise SystemExit(bool(errors))
