# NAS Deploy Files

This folder contains Docker deployment assets for running the solver API on a NAS.

## Files

- `Dockerfile`: API container image
- `docker-compose.yml`: runtime service
- `.env.example`: host bind port config

## Quick use

```bash
cp .env.example .env
docker compose up -d --build
```

For private Tailscale exposure, follow `docs/nas-tailscale.md`.
