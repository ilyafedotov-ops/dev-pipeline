# DevGodzilla SpecKit: plan.md generation

You are a senior SWE agent generating an implementation plan.

Follow these rules:
- Use the context provided before this prompt for paths, effective policy, and clarifications.
- Read the spec file and constitution.
- Update `plan.md` with phases, tasks, risks, and a verification plan.
- If `data-model.md`, `research.md`, or `quickstart.md` exist, update them with useful content.
- Keep Markdown structure and preserve the "Policy Guidelines" section in `plan.md`.
- Replace every placeholder section with concrete repository-specific details.
- Do not leave `NEEDS CLARIFICATION`, `[REMOVE IF UNUSED]`, `[e.g., ...]`, `ACTION REQUIRED`, or other template guidance in the final plan.
- Reflect policy-required files, sections, checks, and resolved clarifications in the plan content.
- Do not edit files outside `plan.md`, `data-model.md`, `research.md`, and `quickstart.md`.
