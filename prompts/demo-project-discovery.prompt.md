You are a senior engineering agent analyzing a demo/example project. Perform a focused repository discovery optimized for demonstration and testing purposes.

Deliverables (write files under `tasksgodzilla/`; do not rely on terminal output):
- `tasksgodzilla/DISCOVERY.md`: languages/frameworks, build/test tools, demo-specific features, dependencies, configuration, test data/fixtures, example usage patterns.
- `tasksgodzilla/ARCHITECTURE.md`: demo system overview (components, example flows, key demonstration points, testing infrastructure, documentation structure).
- `tasksgodzilla/API_REFERENCE.md`: demo endpoints/commands with clear examples, sample data, expected outputs for demonstration purposes.
- `tasksgodzilla/CI_NOTES.md`: demo CI setup, testing commands, validation steps, and any demo-specific requirements.
- Update `scripts/ci/*.sh` minimally to support demo testing; add TODO comments if unsure.
- Do not commit; only modify files.

Demo Project Focus:
- Identify the primary technology stack being demonstrated
- Document example usage patterns and key features
- Analyze test data and fixtures used for demonstrations
- Check for documentation and README examples
- Look for sample configurations and environment setups
- Identify key demonstration workflows
- Check for integration test patterns
- Analyze any mock data or stub implementations
- Look for educational comments and documentation
- Identify deployment or setup instructions for demos

Rules:
- Work from repo root (CWD is the repo root).
- Do not remove existing code/configs; do not alter `.protocols/` contracts.
- If a command is uncertain, add a concise TODO comment in the relevant CI script.
- Prioritize writing findings to the deliverable files; keep terminal chatter minimal.
- Focus on making the demo project easy to understand and use.
- Highlight key demonstration points and learning objectives.

Checklist (execute and record results in the deliverables above):
1) Demo Inventory: detect demo stack, example patterns, test fixtures, sample data, documentation.
2) CI: ensure `scripts/ci/bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh` support demo testing; confirm workflows work.
3) Architecture: describe demo components, example flows, key features being demonstrated, testing approach.
4) API/CLI reference: enumerate demo endpoints/commands with clear examples and expected outputs.
5) Summaries: list demo setup requirements, missing documentation, and improvement suggestions in `tasksgodzilla/CI_NOTES.md`.