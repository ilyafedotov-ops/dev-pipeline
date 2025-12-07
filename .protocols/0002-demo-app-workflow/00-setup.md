# Step 0: Prepare and lock the plan

## Briefing
This is a technical step: commit plan files, publish the branch, and open a PR/MR. These actions must be done before reporting to the user.

## Sub-tasks
1. **Create and save** all protocol artifacts (`plan.md`, `context.md`, `log.md`, `00-setup.md`, and all future step files) in `.protocols/0002-demo-app-workflow/`.
2. **Make the first commit** with these files to branch `0002-demo-app-workflow`.
3. **Create Draft PR/MR** on GitHub or GitLab.
4. **Update `context.md`**: set `Current Step` to `1`, `Status` to `In Progress`, update `Next Action` for Step 1.
5. **Save** the updated `context.md` **without committing** (it will be in the next step’s commit).

## Workflow
1. Execute sub-tasks.
2. Verify: run `lint`, `typecheck`, `test` (scope as needed). Fix failures.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions).
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-0002/00]"`. Push.
5. Report to user using the step report format above.
