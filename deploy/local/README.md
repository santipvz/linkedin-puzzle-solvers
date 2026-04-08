# Local Docker Deployment

This directory contains everything required to run the solver API as a persistent local Docker service.

## Files

- `Dockerfile`: container image for `services/solver_api`.
- `docker-compose.yml`: runtime definition for `solver-api` service.
- `.env.example`: configurable values (bind port and dataset capture paths).

## Step-by-Step Setup

1. Open this directory.
2. Copy environment template.
3. (Optional) adjust port and capture settings.
4. Start service with build.
5. Verify container and health endpoint.

```bash
# from repo root
cd deploy/local
cp .env.example .env
mkdir -p ../../datasets
docker compose up -d --build
```

Verification:

```bash
cd deploy/local
docker compose ps
docker compose logs -f solver-api
curl http://127.0.0.1:18000/health
```

If healthy, configure the extension API URL to:

`http://127.0.0.1:18000`

## Configuration (`.env`)

- `SOLVER_API_BIND_PORT`: host port bound to container `8000` (default `18000`).
- `DATASET_CAPTURE_ENABLED`: `1` to enable start-board capture, `0` to disable.
- `DATASET_CAPTURE_HOST_DIR`: host folder for dataset capture.
- `DATASET_CAPTURE_CONTAINER_DIR`: mount path inside the container.

## Daily Operations

Start service:

```bash
cd deploy/local
docker compose up -d
```

Stop service:

```bash
cd deploy/local
docker compose down
```

Restart service:

```bash
cd deploy/local
docker compose restart solver-api
```

Rebuild after code changes:

```bash
cd deploy/local
docker compose up -d --build
```

## Reboot Behavior

- The service uses `restart: unless-stopped`.
- If Docker starts on system boot, the API container starts automatically.
