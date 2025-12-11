You are a senior polyglot engineering agent. Perform a comprehensive multi-language repository discovery and produce durable docs that future workflows can consume.

Deliverables (write files under `tasksgodzilla/`; do not rely on terminal output):
- `tasksgodzilla/DISCOVERY.md`: all languages/frameworks detected, build/test tools for each language, entrypoints/CLI targets, dependencies across languages, data/config requirements, env vars/secrets, test fixtures, third-party services.
- `tasksgodzilla/ARCHITECTURE.md`: high-level system/flow overview (components across languages, data/control flow between services, runtime/infrastructure, storage/messaging, auth/security, deployment notes).
- `tasksgodzilla/API_REFERENCE.md`: callable surfaces in this repo (HTTP endpoints, CLIs, scripts, functions across all languages); include paths/verbs/flags, sample requests/responses or usage examples, auth/permissions, expected inputs/outputs.
- `tasksgodzilla/CI_NOTES.md`: how CI is wired here (workflows/pipelines), the concrete commands to run for each language (lint/typecheck/test/build), required tools, caches/artifacts, and TODOs/gaps.
- Update `scripts/ci/*.sh` minimally to fit the detected multi-language stack; add TODO comments if unsure.
- Do not commit; only modify files.

Multi-Language Focus:
- Detect all programming languages in use (Python, JavaScript/TypeScript, Go, Java, etc.)
- Identify language-specific frameworks and tools for each
- Check for polyglot build systems (Docker, Bazel, Nx, etc.)
- Analyze inter-service communication patterns (REST, GraphQL, gRPC, message queues)
- Look for shared configuration and environment management
- Identify testing strategies across languages
- Check for consistent linting and formatting across languages
- Analyze database and storage patterns used by different services
- Look for deployment orchestration (Docker Compose, Kubernetes, etc.)
- Identify shared libraries or common code patterns

Rules:
- Work from repo root (CWD is the repo root).
- Do not remove existing code/configs; do not alter `.protocols/` contracts.
- If a command is uncertain, add a concise TODO comment in the relevant CI script.
- Prioritize writing findings to the deliverable files; keep terminal chatter minimal.
- Focus on cross-language integration patterns and consistency.
- Clearly separate findings by language while highlighting integration points.

Checklist (execute and record results in the deliverables above):
1) Multi-Language Inventory: detect all languages, their versions, frameworks, package managers, dependencies, and tools.
2) CI: ensure `scripts/ci/bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh` handle all detected languages; confirm workflows invoke them properly.
3) Architecture: describe how different language components interact, shared data flows, cross-service communication, deployment assumptions.
4) API/CLI reference: enumerate endpoints/commands from all languages with usage examples and integration patterns.
5) Summaries: list remaining TODOs, missing tools/deps for each language, and cross-language integration assumptions in `tasksgodzilla/CI_NOTES.md`.