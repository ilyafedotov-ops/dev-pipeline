# Work Log: 0002 — demo-app-workflow

This is an append-only log:

{add entries about actions, decisions, gotchas, solved issues}

## Step 0 — Prepare and lock the plan (task breakdown)
1. Confirm workspace state: `pwd` matches /home/ilya/Documents/worktrees/0002-demo-app-workflow, on branch `0002-demo-app-workflow`, `git status` clean, `main` untouched.
2. Inventory protocol artifacts in `.protocols/0002-demo-app-workflow/` (plan.md, context.md, log.md, 00-setup.md through 05-finalize.md); create/fix placeholders if any missing, without editing the contract content.
3. Re-read `plan.md` and step files to align with the contract; ensure `context.md` reflects Step 0 before proceeding.
4. Stage protocol artifacts only, then run `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, `scripts/ci/test.sh`; note in log if any are skipped or fail and why.
5. Commit staged protocol artifacts with typed message `feat(<scope>): <subject> [protocol-0002/00]` (e.g., `feat(protocol): lock protocol files [protocol-0002/00]`).
6. Push branch to origin and open a draft PR to `main` summarizing protocol 0002 scope and current status.
7. Update `.protocols/0002-demo-app-workflow/context.md` to `Current Step` 1, `Status` In Progress, and `Next Action` pointing to Step 1; leave this change uncommitted.
8. Append log.md with commit hash, check results, PR link, and any gotchas; verify `main` has no stray files from this branch after push.