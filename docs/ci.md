# CI Notes for DeksdenFlow_Ilyas_Edition_1.0

Both GitHub Actions and GitLab CI call the same shell hooks under `scripts/ci/`. Replace the stubs with real commands for your stack.

## Scripts to implement (fill these)

- `scripts/ci/bootstrap.sh` — install deps, set up toolchains. Examples: `npm ci`, `pip install -r requirements.txt`, `go mod download`, `mvn -B -DskipTests dependency:resolve`.
- `scripts/ci/lint.sh` — static checks/linters. Examples: `npm run lint`, `ruff .`, `golangci-lint run ./...`, `mvn -B -DskipTests checkstyle:check`.
- `scripts/ci/typecheck.sh` — type safety. Examples: `npm run typecheck`, `mypy .`, `tsc --noEmit`, `pyright`, `go vet ./...`.
- `scripts/ci/test.sh` — automated tests. Examples: `npm test`, `pytest`, `go test ./...`, `mvn -B test`.
- `scripts/ci/build.sh` — optional build/package step. Examples: `npm run build`, `go build ./...`, `mvn -B package`.

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

## CI detail checklist (recommended)

1) Bootstrap: install deps, set env (e.g., `NODE_ENV=ci`), verify versions (`node --version`, `python --version`), and cache deps where applicable.
2) Lint: run linters with full exit-on-error; surface reports if available.
3) Typecheck: run type checker separately from lint to catch typing issues explicitly.
4) Test: run unit/integration tests; consider `CI=true` flags; produce coverage if desired.
5) Build: optional packaging or artifact build; fail fast on errors.
6) Skip behavior: scripts are optional; missing/executable check is already handled in workflows.
7) Artifacts: if your stack supports reports (e.g., JUnit XML), add upload steps in workflow as needed.

## Caching

Add cache steps per stack as needed (npm, pip, pnpm, cargo, go build cache, Maven/Gradle). Keep cache keys stable across both CI systems for consistency.
