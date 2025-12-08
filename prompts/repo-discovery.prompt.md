You are a senior engineering agent. Perform a full repository discovery and produce durable docs that future workflows can consume (generic across any stack).

Deliverables (write files under `tasksgodzilla/`; do not rely on terminal output):
- `tasksgodzilla/DISCOVERY.md`: languages/frameworks, build/test tools, entrypoints/CLI targets, dependencies, data/config requirements, env vars/secrets, test fixtures, third-party services.
- `tasksgodzilla/ARCHITECTURE.md`: high-level system/flow overview (components, data/control flow, runtime/infrastructure, storage/messaging, auth/security, deployment notes).
- `tasksgodzilla/API_REFERENCE.md`: callable surfaces in this repo (HTTP endpoints, CLIs, scripts, functions); include paths/verbs/flags, sample requests/responses or usage examples, auth/permissions, expected inputs/outputs.
- `tasksgodzilla/CI_NOTES.md`: how CI is wired here (workflows/pipelines), the concrete commands to run (lint/typecheck/test/build), required tools, caches/artifacts, and TODOs/gaps.
- Update `scripts/ci/*.sh` minimally to fit the detected stack; add TODO comments if unsure.
- Do not commit; only modify files.

Rules:
- Work from repo root (CWD is the repo root).
- Do not remove existing code/configs; do not alter `.protocols/` contracts.
- If a command is uncertain, add a concise TODO comment in the relevant CI script.
- Prioritize writing findings to the deliverable files; keep terminal chatter minimal.

Checklist (execute and record results in the deliverables above):
1) Inventory: detect languages/build tools (`package.json`, `pyproject.toml`, `pom.xml`, `go.mod`, PowerShell/Make/Cargo/etc.), data/fixtures, env vars/secrets, external services.
2) CI: ensure `scripts/ci/bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh` match the actual stack; confirm `.github/workflows/ci.yml` / `.gitlab-ci.yml` invoke them.
3) Architecture: describe components, flows, deployment/runtime assumptions; note storage, messaging, auth/security patterns.
4) API/CLI reference: enumerate endpoints/commands with usage examples and auth/inputs/outputs.
5) Summaries: list remaining TODOs, missing tools/deps, and assumptions in `tasksgodzilla/CI_NOTES.md`.
