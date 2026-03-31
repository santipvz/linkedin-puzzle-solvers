# Local Deploy Files

This folder contains Docker deployment assets for running the solver API on your local PC.

## Files

- `Dockerfile`: API container image
- `docker-compose.yml`: runtime service
- `.env.example`: host bind port config

## Quick start

```bash
cp .env.example .env
docker-compose up -d --build
```

## Keep working after reboot

- Service uses `restart: unless-stopped`, so Docker starts it automatically after reboot.
- Ensure Docker itself starts on boot.

## Useful commands

```bash
docker-compose ps
docker-compose logs -f solver-api
curl -s http://127.0.0.1:18000/health
```
