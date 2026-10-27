# CI

CI runs on PRs to `main`/`develop`, pushes to those branches, and manual dispatches. New commits cancel superseded runs. The `gitflow` check validates PR targets.

The quality job loads two cached Docker environments: `ci` has Python, Node, OCR fonts, and test tools; `dependencies` has production libraries. It mounts the current checkout, runs `scripts/quality_check.py`, then packages and checks the current production image using the saved dependency image.

The cache key includes the Dockerfile, `.dockerignore`, architecture, and all requirements files. A miss builds and saves the environments. Bump `solver-ci-v1` in the workflow to refresh base images without changing requirements. Cache eviction also triggers a rebuild.

Run the same checks locally:

```bash
docker build --target ci -f deploy/local/Dockerfile -t solver-ci-env .
docker run --rm --user "$(id -u):$(id -g)" --volume "$PWD:/app" solver-ci-env
```

The default Dockerfile target remains the production image used by Compose. `RUNTIME_BASE` lets CI reuse its saved production environment.
