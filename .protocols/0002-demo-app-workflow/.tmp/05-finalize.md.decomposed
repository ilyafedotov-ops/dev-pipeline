# Step 05: Finalize

## Briefing
- **Goal:** Close out the protocol with clear status, documentation, and PR readiness.
- **Key files:**
  - `context.md`, `log.md`
  - PR description and metadata
- **Additional info:** Ensure all instructions from the workflow report format are satisfied; no untracked files.

## Sub-tasks
1. Documentation wrap-up
   - Append final reasoning and outcomes to `log.md` (decisions, test results, any deviations).
   - Update `context.md` with the final state, noting `Current Step`, `Next Action`, and any remaining follow-ups.
2. Repository hygiene and PR posture
   - Confirm `git status` is clean; resolve or commit any staged/unstaged changes.
   - Ensure the branch is pushed; flip PR from Draft to Ready for Review and refresh PR metadata (title, description, checklist).
3. Freshness checks
   - Re-run lightweight validation as needed (e.g., targeted `lint`, `typecheck`, `test` commands) to ensure no drift since the last run.
   - Capture outputs or note “not run” with justification in `log.md`.
4. Final user report preparation
   - Draft the protocol report covering accomplishments, checks executed (pass/fail with reasons), git status (branch, push), working directory, and protocol state per the required format.
5. Follow-ups and ownership
   - Enumerate unresolved items or risks with named owners or next-step suggestions.
   - Link any tracking issues or TODOs in `log.md`/PR description for handoff clarity.

## Workflow
1. Execute sub-tasks in order, updating `log.md` and `context.md` as changes occur.
2. Verify: run `lint`, `typecheck`, `test` (scope as needed). Fix failures or document deferrals with rationale.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions).
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-0002/05]"`. Push.
5. Report to user using the step report format above.