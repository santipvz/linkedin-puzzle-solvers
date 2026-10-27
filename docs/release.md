# Releases

Follow [Gitflow](https://nvie.com/posts/a-successful-git-branching-model/): `develop` integrates changes; `main` holds releases.

1. Create `release/<version>` from current `develop`. For an urgent production fix, create `hotfix/<topic>` from `main` instead.
2. Update the extension manifest and API version together. Run `python3 scripts/quality_check.py` and manually check affected games.
3. Open a PR to `main`. Wait for `gitflow` and `solver-and-extension-smoke`, then merge with a **merge commit**.
4. Open a synchronization PR from `main` to `develop` and merge it. This includes release preparation and hotfix changes.
5. Tag the merged commit on `main` as `v<version>` and create a GitHub release with changes and validation notes.

Package the extension from the repository root:

```bash
(cd extension && zip -r ../linkedin-puzzle-solver-extension.zip .)
```

Attach the zip to the release. The API is deployed with [Docker Compose](../deploy/local/README.md).
