# Step 04: Validate and stabilize

## Briefing
- **Goal:** Confirm the demo workflow results, run CI checks, and address issues or document gaps.
- **Key files:**
  - `log.md` entries from the run
  - CI scripts: `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, `scripts/ci/test.sh`
  - Any modified source files under `tasksgodzilla/` or scripts
- **Additional info:** Capture evidence (screens, logs, artifacts) showing success or failures. Prefer fixes where feasible; otherwise, document follow-ups.

## Sub-tasks
1. Collect run evidence: gather logs/output from the demo run (console transcripts, stored artifacts, screenshots) and note where they live.
2. Validate results: compare artifacts against expected outcomes (e.g., persisted DB/queue entries, generated files, HTTP responses); flag any mismatches or errors seen in logs.
3. Triage deviations: for each issue, capture reproduction steps, relevant stack traces/log excerpts, and initial hypothesis.
4. Run CI locally in order, capturing pass/fail: `scripts/ci/lint.sh`, then `scripts/ci/typecheck.sh`, then `scripts/ci/test.sh`.
5. Address failures: apply minimal fixes; rerun only the failing script(s) until green. If blocked, record the blocker with repro and scope of impact.
6. Update docs/configs as needed: reflect any behavior changes, env var tweaks, or workarounds in README/snippets or config notes.
7. Summarize in `log.md`: evidence reviewed, CI results, fixes applied, remaining risks/blockers, and pointers to artifacts.

## Workflow
1. Execute sub-tasks.
2. Verify: run `lint`, `typecheck`, `test` (scope as needed). Fix failures.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions).
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-0002/04]"`. Push.
5. Report to user using the step report format above.