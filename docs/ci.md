# DevGodzilla CI Notes

> Status: Active
> Scope: Current CI scripts, local parity, and live harness notes
> Source of truth: `scripts/ci/*.sh`, `.github/workflows/`, `tests/e2e/`
> Last updated: 2026-04-19

## CI Scripts

- `scripts/ci/bootstrap.sh`
  - Creates `.venv`
  - Installs `requirements.txt` plus `ruff`
- `scripts/ci/lint.sh`
  - Runs `ruff check devgodzilla windmill scripts tests --select E9,F63,F7,F82`
  - Runs `scripts/ci/devgodzilla_standalone_guard.sh`
- `scripts/ci/typecheck.sh`
  - Runs `compileall` over runtime directories
  - Performs import smoke for key modules
- `scripts/ci/test.sh`
  - Runs the deterministic backend unit slice: `tests/test_devgodzilla_*.py -k "not integration"`
  - Optionally runs real-agent E2E coverage only when `DEVGODZILLA_RUN_E2E_REAL_AGENT=1`
- `scripts/ci/test_frontend.sh`
  - Runs frontend Vitest coverage via `pnpm test:run`
  - Runs Playwright smoke coverage via `pnpm test:e2e:smoke`
- `scripts/ci/build.sh`
  - Builds the Docker image when Docker is available
  - Falls back to compose validation or a skipped status when container tooling is unavailable

## Local Parity

Typical backend parity sequence:

```bash
scripts/ci/bootstrap.sh
scripts/ci/lint.sh
scripts/ci/typecheck.sh
scripts/ci/test.sh
scripts/ci/build.sh
```

Frontend parity sequence:

```bash
scripts/ci/test_frontend.sh
```

Or manually:

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm test:run
pnpm test:e2e:smoke
```

## Operational Notes

- CI wrappers may report status through `scripts/ci/report.sh` when present.
- `scripts/ci/test.sh` does not require a real agent binary unless `DEVGODZILLA_RUN_E2E_REAL_AGENT=1`.
- Full-Docker local development is available via `docker-compose.yml` and `docker-compose.local.yml`.
- The explicit host-backed proxy topology is defined in `docker-compose.devgodzilla.yml` and `nginx.local.conf`.

If you want a lighter Docker backend image and do not need in-container CLI agents:

```bash
export INSTALL_AGENT_CLIS=0
docker compose -f docker-compose.local.yml up -d --build devgodzilla-api
```

For `opencode` in a runtime that needs it:

```bash
opencode auth login
```

## Live Harness

Live harness entrypoint:

- `scripts/ci/test-harness-live.sh`

Default GitHub repo coverage:

- `HARNESS_GITHUB_OWNER=ilyafedotov-ops`
- `HARNESS_GITHUB_REPOS=test-glm5-demo,SimpleAdminReporter,demo-spring`

Automation workflow:

- `.github/workflows/live-harness.yml`

Manual examples:

```bash
# default matrix
scripts/ci/test-harness-live.sh

# single scenario
HARNESS_SCENARIO=live_onboarding_demo_spring scripts/ci/test-harness-live.sh

# one-off repo URL override
HARNESS_REPO_URL_OVERRIDE=https://github.com/ilyafedotov-ops/demo-spring.git \
scripts/ci/test-harness-live.sh

# use dummy engine
HARNESS_STEP_ENGINE=dummy scripts/ci/test-harness-live.sh
```

Key harness environment variables:

- `DEVGODZILLA_RUN_E2E_HARNESS=1`
- `DEVGODZILLA_DB_URL` or `DEVGODZILLA_DB_PATH`
- `HARNESS_GITHUB_OWNER`
- `HARNESS_GITHUB_REPOS`
- `HARNESS_REPO_URL_OVERRIDE`
- `HARNESS_SCENARIO`
- `HARNESS_CONTINUE_ON_ERROR`
- `HARNESS_ONBOARD_MODE`
- `HARNESS_STEP_ENGINE`
- `HARNESS_FEATURE_CYCLES`
- `HARNESS_WINDMILL_AUTO_IMPORT`
- `HARNESS_WINDMILL_HEARTBEAT_TIMEOUT_SECONDS`
- `WINDMILL_JOB_TIMEOUT_SECONDS`

## Adding New Harness Coverage

Contracts:

- Schema: `schemas/e2e-workflow-harness.schema.json`
- Scenarios: `tests/e2e/scenarios/*.json`
- Adapters: `tests/e2e/adapters/*.adapter.json`

Typical flow:

1. Copy an existing scenario JSON in `tests/e2e/scenarios/`.
2. Set `scenario_id`, `repo.owner`, `repo.name`, and `adapter_id`.
3. Prefer `owner` plus `name`; omit `url` unless a non-default Git URL is required.
4. Copy or create the matching adapter JSON in `tests/e2e/adapters/`.
5. Validate loader coverage with `pytest -q tests/e2e/test_harness_scenario_loader.py`.
6. Run a focused live harness pass with `HARNESS_SCENARIO=<scenario_id> scripts/ci/test-harness-live.sh`.

## Diagnostics and Monitoring

Harness diagnostics are written under:

- `runs/harness/<timestamp>-<scenario_id>/diagnostics/`

Useful monitoring commands:

```bash
RUN_DIR="$(ls -td runs/harness/* | head -n1)"

tail -F "$RUN_DIR/diagnostics/events.jsonl" | jq -c
tail -F "$RUN_DIR/diagnostics/events.jsonl" | jq -c 'select(.event_type|test("protocol_cycle_|substage_"))'
tail -F "$RUN_DIR/diagnostics/events.jsonl" | jq -c 'select(.event_type|test("^onboarding_"))'
tail -F "$RUN_DIR"/diagnostics/cli-*.log
tail -F "$RUN_DIR"/diagnostics/windmill-job-*.log
```

DB alignment note:

- Windmill onboarding uses the backend API DB.
- Harness CLI commands use the local process DB config.
- If those differ, onboarding can enqueue successfully while later stages fail against missing project state.

Align `DEVGODZILLA_DB_URL` or `DEVGODZILLA_DB_PATH` across both runtimes when debugging harness issues locally.
