# Releases

Follow [Gitflow](https://nvie.com/posts/a-successful-git-branching-model/): `main` is the default branch and stable source for distribution; `develop` integrates changes for the next release.

1. Create `release/<version>` from current `develop`. For an urgent production fix, create `hotfix/<topic>` from `main` instead.
2. Update the extension manifest and API version together. Run `python3 scripts/quality_check.py` and manually check affected games.
3. Open a PR to `main`. Wait for `gitflow` and `solver-and-extension-smoke`, then merge with a **merge commit**.
4. Open a synchronization PR from `main` to `develop` and merge it. This includes release preparation and hotfix changes.
5. Tag the merged commit on `main` as `v<version>` and create a GitHub release with changes and validation notes.

Documentation-only updates can use `release/<topic>` without a version bump or a versioned release. Merge to `main` and sync back to `develop` as above.

## Distribute the extension

Package from the tagged release on `main`, not from `develop`. From a clean checkout:

```bash
git fetch origin --tags
git switch --detach v<version>
(cd extension && zip -r ../linkedin-puzzle-solver-extension.zip .)
```

Attach the zip to the GitHub release. For a local installation, use `extension/` from `main` or the release tag, reload the extension, and refresh the game tabs.

Merging into `main` does not update installed extensions or publish to browser stores. Store publication and Firefox signing are separate manual steps; no workflow currently automates them. The API is deployed with [Docker Compose](../deploy/local/README.md).
