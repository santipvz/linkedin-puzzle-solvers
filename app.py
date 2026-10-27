"""Vercel ASGI entrypoint. The local Uvicorn entrypoint remains supported."""
import os

# Set before workers import NumPy/OpenCV. A solve should not spawn a BLAS pool.
for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from services.solver_api.app.main import app  # noqa: F401
