# CI Notes for DeksdenFlow_Ilyas_Edition_1.0

Both GitHub Actions and GitLab CI call the same shell hooks under `scripts/ci/`. Replace the stubs with real commands for your stack.

## Scripts to implement

- `scripts/ci/bootstrap.sh` — install deps, set up toolchains. Examples: `npm ci`, `pip install -r requirements.txt`, `go mod download`.
- `scripts/ci/lint.sh` — static checks/linters. Examples: `npm run lint`, `ruff .`, `golangci-lint run ./...`.
- `scripts/ci/typecheck.sh` — type safety. Examples: `npm run typecheck`, `mypy .`, `tsc --noEmit`.
- `scripts/ci/test.sh` — automated tests. Examples: `npm test`, `pytest`, `go test ./...`.
- `scripts/ci/build.sh` — optional build/package step.

Each script should exit non-zero on failure and print useful logs. The pipelines skip a step if the script is missing or not executable, so you can adopt gradually.

## Local parity

Run the same scripts locally before pushing:

```bash
./scripts/ci/bootstrap.sh
./scripts/ci/lint.sh
./scripts/ci/typecheck.sh
./scripts/ci/test.sh
./scripts/ci/build.sh
```

## GitHub Actions

- File: `.github/workflows/ci.yml`
- Jobs: `checks` (bootstrap → lint → typecheck → test → build)
- Triggered on `push` and `pull_request`.

## GitLab CI

- File: `.gitlab-ci.yml`
- Stages: `bootstrap`, `lint`, `typecheck`, `test`, `build`
- Jobs mirror the GitHub Actions order and reuse the same scripts.

## Caching

Add cache steps per stack as needed (npm, pip, pnpm, cargo, go build cache, etc.). Keep cache keys stable across both CI systems for consistency.
