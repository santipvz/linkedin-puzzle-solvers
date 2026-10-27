from pathlib import Path

from .adapters.captures import FileCaptureStore
from .adapters.http import create_http_app
from .adapters.memory import MemorySolutionCache
from .adapters.workers import WorkerSolver
from .application.solve_puzzle import SolvePuzzle
from .puzzle_registry import PUZZLE_DEFINITIONS
from .settings import Settings


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    service = SolvePuzzle(
        solver=WorkerSolver(
            worker_filenames={puzzle.key: puzzle.worker_filename for puzzle in PUZZLE_DEFINITIONS},
            workers_directory=Path(__file__).parent / "workers",
            mode=settings.worker_mode,
            timeout=settings.worker_timeout,
        ),
        cache=MemorySolutionCache(),
        captures=FileCaptureStore(settings.capture_directory, settings.repo_root, settings.capture_enabled),
        cache_revisions={puzzle.key: puzzle.cache_revision for puzzle in PUZZLE_DEFINITIONS},
    )
    return create_http_app(service, tuple(service.cache_revisions), settings.cors_origins, settings.cors_origin_regex)
