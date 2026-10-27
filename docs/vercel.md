# Vercel

The online API runs the same solvers as the local service. The extension's **Online** option uses `https://linkedin-puzzle-solvers.vercel.app`; **Local / custom API** preserves your existing URL. Online sends the board image over HTTPS; board captures are not archived by default.

## Deploy

Use Node/npm and a Vercel account with access to the project:

```bash
npx vercel@65.4.0 link --project linkedin-puzzle-solvers
npx vercel@65.4.0 deploy
```

This creates a protected preview. Use `npx vercel@65.4.0 curl /health --deployment <preview-url>` to test it while authenticated. Run full quality checks before promoting a release from `main` with `npx vercel@65.4.0 deploy --prod`.

Validate the public API with the six tracked game samples:

```bash
python3 scripts/api_endpoint_smoke.py --base-url https://linkedin-puzzle-solvers.vercel.app
```

CI also runs `python3 scripts/api_endpoint_smoke.py --hosted` to solve all six samples with the Vercel profile and bundled fonts before merging.

## Runtime

- `app.py` is the ASGI entrypoint. Python 3.12 and API dependencies are declared in `pyproject.toml`; a test keeps them aligned with the Docker requirements. Matplotlib remains an optional visualization dependency of the local root requirements.
- `.vercelignore` excludes development files, examples, captures, secrets and extension assets. Tango templates, OCR fonts and Wend dictionaries remain in the deployment.
- Open font files and their license notices live in `core/assets/fonts/`. Vercel uses this deterministic font set; local installations keep their system font selection and fall back to the bundled fonts when needed.
- `VERCEL=1` disables capture archiving by default, caps uploads at 4 MiB (below Vercel's 4.5 MB request limit), and allows one active solver per instance. Oversized online captures are JPEG-compressed by the extension without changing dimensions; images still over the limit are rejected.
- Solvers run in isolated subprocesses with a 60-second timeout and one BLAS thread. OCR caches and temporary images use `/tmp`; temporary uploads are removed after each solve. The function has a 120-second limit.
- Busy instances return HTTP 503 with `Retry-After`. This is an instance resource limit, not a global request quota: Vercel may start additional instances. The online service is a trial; measure usage before opening it to a large audience.

Local Uvicorn and Docker commands remain supported. Do not embed Vercel deployment bypass secrets or account credentials in the extension.
