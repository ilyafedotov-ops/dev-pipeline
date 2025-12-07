You are a senior engineering agent. Perform a quick discovery of this repository and prepare it for TasksGodzilla_Ilyas_Edition_1.0:

Goals:
1) Identify stack/framework/build tool (Java/JS/Python/etc.) and existing CI signals.
2) Propose and apply minimal CI commands to `scripts/ci/*.sh` (lint/typecheck/test/build) based on the detected stack. If unsure, leave clear TODOs.
3) Verify/update `.github/workflows/ci.yml` and `.gitlab-ci.yml` to call these scripts (already wired to skip missing scripts).
4) Leave the repo uncommitted; report changes at the end.

Rules:
- Work from the repo root (CWD given by the runner).
- Do not remove existing user code/configs.
- Keep changes minimal and stack-appropriate.
- If you can’t infer a command, add a short TODO comment in the script explaining what to fill.
- Do not alter plan/step contracts in `.protocols/` if present.

Checklist:
1) Inventory: detect language/build (e.g., `package.json`, `pyproject.toml`, `pom.xml`, `go.mod`, etc.).
2) Update CI scripts:
   - `scripts/ci/bootstrap.sh` (install deps)
   - `scripts/ci/lint.sh`
   - `scripts/ci/typecheck.sh`
   - `scripts/ci/test.sh`
   - `scripts/ci/build.sh` (optional; skip if not applicable)
3) Confirm workflows exist; no further edits needed unless paths are wrong.
4) Print a summary of changes and remaining TODOs.
