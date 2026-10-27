# CI can reuse the saved dependency image when packaging the current checkout.
ARG RUNTIME_BASE=dependencies

FROM python:3.12-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY services/solver_api/requirements.txt /tmp/requirements.txt

RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

# Reusable CI environment: no application source is baked into this stage.
# CI mounts the current checkout so the same image can test subsequent commits.
FROM dependencies AS ci

COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt requirements-dev.txt /tmp/ci-requirements/
COPY services/solver_api/requirements.txt /tmp/ci-requirements/services/solver_api/requirements.txt

RUN pip install -r /tmp/ci-requirements/requirements-dev.txt && node --version

ENV MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONHASHSEED=0

CMD ["python", "scripts/quality_check.py"]

# Keep the final/default target as the production image used by Docker Compose.
FROM ${RUNTIME_BASE} AS runtime

COPY . /app

WORKDIR /app/services/solver_api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
