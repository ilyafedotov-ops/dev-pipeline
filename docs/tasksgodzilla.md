# TasksGodzilla_Ilyas_Edition_1.0 Overview

TasksGodzilla_Ilyas_Edition_1.0 is an agent-first workflow tuned for doing changes in parallel streams with clear contracts. The public series (7 posts) covers:

1. Git workflow — branches/worktrees plus protocol numbering.
2. Contexts — gather all signals before acting.
3. Protocol: discussion — negotiate scope and constraints.
4. Protocol: plan lock-in — freeze the contract for the step-by-step work.
5. Protocol: execution — deliver against the locked plan.
6. Protocol: review & merge — independent QA with explicit gates.
7. Organizational wrap-up — close the loop and clean up.

## Principles

- Parallelism with isolation: each stream has its own protocol directory and branch.
- Protocols are contracts: plans live in `.protocols/NNNN-[task]/` and are not rewritten mid-step.
- Logs over memory: `log.md` and `context.md` keep the ground truth.
- Bias for simple, modern solutions: remove legacy, prefer clean implementations.
- Tests as part of the flow: each step mandates lint/typecheck/test before commit.

## Provided prompts

- `prompts/protocol-new.prompt.md` — start a new protocol: branch+worktree, plan, PR draft.
- `prompts/protocol-resume.prompt.md` — restore context and continue a protocol.
- `prompts/protocol-review-merge.prompt.md` — QA/review process before merge.
- `prompts/protocol-review-merge-resume.prompt.md` — restore context mid-review.
- `prompts/project-init.prompt.md` — bootstrap a fresh repo with this structure, CI, and prompts.

## How to adapt

- Keep `.protocols/` under version control; mirror it in worktrees to keep state local to each stream.
- Update `scripts/ci/*` to run stack-specific checks, but keep job names and structure stable for both GitHub and GitLab.
- When adding new prompts, follow the same style: explicit phases, clear stop conditions, and reproducible steps.

## PR creation (automated)
- CLI: run `scripts/protocol_pipeline.py --pr-platform github|gitlab` to auto-commit the plan, push the protocol branch, and open a Draft PR/MR (uses `gh`/`glab` when installed; otherwise falls back to GitHub REST with `GITHUB_TOKEN`/`GH_TOKEN`).
- Backend/API: call `POST /protocols/{id}/actions/open_pr` to enqueue `open_pr_job`; the worker will push the branch and open the PR/MR using the same fallbacks.
- Commits should primarily contain code/test changes associated with protocol steps; keep `.protocols` updates focused on state/logs.
