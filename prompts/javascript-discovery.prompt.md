You are a senior JavaScript/Node.js engineering agent. Perform a comprehensive JavaScript repository discovery and produce durable docs that future workflows can consume.

Deliverables (write files under `tasksgodzilla/`; do not rely on terminal output):
- `tasksgodzilla/DISCOVERY.md`: Node.js version, frameworks (Express/Koa/Next.js/React/Vue), package management (npm/yarn/pnpm), bundlers, dependencies, env vars/secrets, test fixtures, third-party services.
- `tasksgodzilla/ARCHITECTURE.md`: high-level system/flow overview (components, modules, data/control flow, runtime/infrastructure, database/storage, auth/security, deployment notes).
- `tasksgodzilla/API_REFERENCE.md`: callable surfaces in this repo (HTTP endpoints, CLI commands, functions/exports); include paths/verbs/flags, sample requests/responses or usage examples, auth/permissions, expected inputs/outputs.
- `tasksgodzilla/CI_NOTES.md`: how CI is wired here (workflows/pipelines), the concrete commands to run (lint/typecheck/test/build), required tools, caches/artifacts, and TODOs/gaps.
- Update `scripts/ci/*.sh` minimally to fit the detected JavaScript stack; add TODO comments if unsure.
- Do not commit; only modify files.

JavaScript-Specific Focus:
- Detect Node.js version requirements (package.json, .nvmrc)
- Identify frameworks (Express, Koa, Next.js, React, Vue, Angular, etc.)
- Check for package managers (npm, yarn, pnpm) and lockfiles
- Analyze bundlers and build tools (webpack, vite, rollup, parcel)
- Look for TypeScript configuration and usage
- Identify testing frameworks (jest, mocha, vitest, cypress)
- Check for linting tools (eslint, prettier)
- Analyze database integrations (mongoose, sequelize, prisma)
- Look for frontend/backend separation patterns
- Check for serverless or edge deployment patterns

Rules:
- Work from repo root (CWD is the repo root).
- Do not remove existing code/configs; do not alter `.protocols/` contracts.
- If a command is uncertain, add a concise TODO comment in the relevant CI script.
- Prioritize writing findings to the deliverable files; keep terminal chatter minimal.
- Focus on JavaScript/Node.js-specific patterns and best practices.

Checklist (execute and record results in the deliverables above):
1) JavaScript Inventory: detect Node.js version, frameworks, package managers, bundlers, dependencies, testing tools.
2) CI: ensure `scripts/ci/bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh` match the JavaScript stack; confirm workflows invoke them.
3) Architecture: describe JavaScript modules/components, data flows, database patterns, frontend/backend separation, deployment assumptions.
4) API/CLI reference: enumerate JavaScript endpoints/commands with usage examples and type definitions.
5) Summaries: list remaining TODOs, missing JavaScript tools/deps, and assumptions in `tasksgodzilla/CI_NOTES.md`.