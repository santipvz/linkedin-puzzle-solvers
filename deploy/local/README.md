# Local Deploy Files

This folder contains Docker deployment assets for running the solver API on your local PC.

## Files

- `Dockerfile`: API container image
- `docker-compose.yml`: runtime service
- `.env.example`: host bind port config

## Quick start

```bash
cp .env.example .env
mkdir -p ../../datasets
docker-compose up -d --build
```

## Keep working after reboot

- Service uses `restart: unless-stopped`, so Docker starts it automatically after reboot.
- Ensure Docker itself starts on boot.
- Board capture dataset persists on host at `datasets` via bind mount.

## Dataset path config

- `DATASET_CAPTURE_ENABLED`: set `0` to disable capture.
- `DATASET_CAPTURE_HOST_DIR`: host directory for captures.
- `DATASET_CAPTURE_CONTAINER_DIR`: container path used by API (`DATASET_CAPTURE_DIR`).

## Useful commands

```bash
docker-compose ps
docker-compose logs -f solver-api
curl -s http://127.0.0.1:18000/health
```
