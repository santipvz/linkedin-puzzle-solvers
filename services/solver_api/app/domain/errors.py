class SolverError(Exception):
    """An application failure independent of its transport."""


class EmptyImage(SolverError):
    pass


class ImageTooLarge(SolverError):
    pass


class UnsupportedImage(SolverError):
    pass


class UnknownPuzzle(SolverError):
    pass


class SolverTimeout(SolverError):
    pass


class SolverBusy(SolverError):
    pass


class WorkerFailure(SolverError):
    pass
