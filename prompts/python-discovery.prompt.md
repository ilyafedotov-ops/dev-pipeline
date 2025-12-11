You are a senior Python engineering agent. Perform a comprehensive Python repository discovery and produce durable docs that future workflows can consume.

Deliverables (write files under `tasksgodzilla/`; do not rely on terminal output):
- `tasksgodzilla/DISCOVERY.md`: Python version, frameworks (Django/Flask/FastAPI), package management (pip/poetry/pipenv), virtual environments, dependencies, data/config requirements, env vars/secrets, test fixtures, third-party services.
- `tasksgodzilla/ARCHITECTURE.md`: high-level system/flow overview (modules, packages, data/control flow, runtime/infrastructure, database/ORM, auth/security, deployment notes).
- `tasksgodzilla/API_REFERENCE.md`: callable surfaces in this repo (HTTP endpoints, CLI commands, functions/classes); include paths/verbs/flags, sample requests/responses or usage examples, auth/permissions, expected inputs/outputs.
- `tasksgodzilla/CI_NOTES.md`: how CI is wired here (workflows/pipelines), the concrete commands to run (lint/typecheck/test/build), required tools, caches/artifacts, and TODOs/gaps.
- Update `scripts/ci/*.sh` minimally to fit the detected Python stack; add TODO comments if unsure.
- Do not commit; only modify files.

Python-Specific Focus:
- Detect Python version requirements (pyproject.toml, setup.py, requirements.txt)
- Identify web frameworks (Django, Flask, FastAPI, etc.)
- Check for package management tools (pip, poetry, pipenv, conda)
- Analyze testing frameworks (pytest, unittest, nose)
- Look for type checking (mypy, pyright)
- Identify linting tools (flake8, pylint, ruff)
- Check for virtual environment configurations
- Analyze database integrations (SQLAlchemy, Django ORM, etc.)
- Look for async patterns (asyncio, aiohttp)

Rules:
- Work from repo root (CWD is the repo root).
- Do not remove existing code/configs; do not alter `.protocols/` contracts.
- If a command is uncertain, add a concise TODO comment in the relevant CI script.
- Prioritize writing findings to the deliverable files; keep terminal chatter minimal.
- Focus on Python-specific patterns and best practices.

Checklist (execute and record results in the deliverables above):
1) Python Inventory: detect Python version, frameworks, package managers, dependencies, virtual environments, testing tools.
2) CI: ensure `scripts/ci/bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh` match the Python stack; confirm workflows invoke them.
3) Architecture: describe Python modules/packages, data flows, database patterns, async patterns, deployment assumptions.
4) API/CLI reference: enumerate Python endpoints/commands with usage examples and type hints.
5) Summaries: list remaining TODOs, missing Python tools/deps, and assumptions in `tasksgodzilla/CI_NOTES.md`.