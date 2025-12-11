Great, we have discussed the details. Your task is to finalize the plan and prepare an isolated workspace ("sandbox").

## Required inputs
- Protocol: NNNN (next number) and `Task-short-name`
- Base branch: `main` (confirm if different)
- CI target: GitHub, GitLab, or both
- PR/MR tooling: `gh` CLI available? GitLab? (if not, plan for manual creation)

Follow this strict algorithm.

### Phase 1: Environment check and preparation

1. **Verify Git state and starting conditions:**
   * Ensure current branch is `main`.
   * Ensure working tree is clean. If not, ask the user what to do.
   * Run `git fetch origin` to refresh remote info.
   * Compare local `main` with `origin/main`. If local is behind, **stop and ask the user to update** before continuing.
   * Run current checks (`typecheck`, `lint`). If they fail, **stop and report**; continue only after fixes.
   * If you plan to use `gh`, run `which gh`. If missing, be ready to create PR manually or use GitLab MR.

2. **Determine the new protocol number (NNNN):**
   * Read the contents of `../worktrees/` (if it exists).
   * Read the contents of `.protocols/`.
   * Take the max existing number and use the next one.

### Phase 2: Create isolated workspace

3. **Create the branch and worktree:**
   * Command: `git worktree add --checkout -b NNNN-[Task-short-name] ../worktrees/NNNN-[Task-short-name] origin/main`
   * `NNNN-[Task-short-name]` is the protocol name.

4. **Move into the new worktree (this is now CWD):**
   * All further commands run from here.
   * Note absolute paths for `PROJECT_ROOT` (main repo) and `CWD` (worktree).

### Phase 3: Create protocol artifacts

5. **Create protocol structure:**
   * In CWD, create `.protocols/NNNN-[Task-short-name]/`. This is the protocol root.
   * Ensure a protocol with this number does not already exist.
   * Inside, create:
     * `plan.md` — main plan.
     * `context.md` — current state.
     * `log.md` — work log.
     * `00-setup.md` — detailed plan for step 0.
     * `XX-{step-name}.md` — detailed plan per subsequent step, where XX is step number.

6. **Fill initial content:**
   * Write your generated detailed plan into `plan.md`, `00-setup.md`, and other step files using the **STRICT STRUCTURE** below.
   * Pay attention to `{curly braces}` placeholders that must be filled.
   * Each step must be self-contained and detailed.

7. **Planning principles:**
   * **Balance and simplicity:** avoid overengineering; use the simplest solution that works.
   * **No legacy:** do not carry old approaches; fresh codebase decisions are allowed.
   * **Coding standards:** follow project lint/format/JSDoc (or equivalents).
   * **Memory Bank Bible:** keep docs up to date and atomic.
   * **Quality tests:** balanced coverage (positive/negative/boundaries) using existing helpers.
   * **Detail:** plans must be executable without this chat; decompose steps appropriately.

8. **Make the first commit:**
   * `git add .protocols/NNNN-[Task-short-name]`
   * Commit message: `feat(protocol): add plan for NNNN-[Task-short-name] [protocol-NNNN/00]`

### Phase 4: Publish and report

8. **Create Draft PR/MR:**
   * `git push --set-upstream origin NNNN-[Task-short-name]`
   * GitHub (if `gh` available):
     `gh pr create --draft --title "WIP: NNNN - [Task-short-name]" --body "This PR is being worked on according to protocol NNNN. See the protocol directory for the detailed plan: .protocols/NNNN-[Task-short-name]/"`
   * GitLab: create a Merge Request with base `main`, title `WIP: NNNN - [Task-short-name]`, link to `.protocols/NNNN-[Task-short-name]/`.
   * If no CLI, describe manual PR/MR creation to the user and share the URL.

### Phase 5: Finish Step 0

9. **Finalize step 0:**
   * After PR/MR, update `context.md`:
     * `Current Step`: `1`
     * `Status`: `In Progress`
     * `Last Action Summary`: "Step 0 done: workspace created, plan committed, PR opened."
     * `Next Action`: "Start Step 1 (see `01-[step-name].md`)."
   * Save the updated `context.md` **without a commit** (to be committed in the next step).

10. **Present result:**
    * Report completion.
    * Show contents of `plan.md` and `00-setup.md` for user confirmation.
    * If plan changes with the user, fix via amend.

---
### TEMPLATES FOR PROTOCOL FILES
---

#### `plan.md`

```markdown
# {NNNN — Short task name}

## ADR-style Summary:
- **Context**: ...
- **Problem Statement**: ...
- **Decision**: ...
- **Alternatives**: ...
- **Consequences**: ...

---

## High-Level Plan:
This section is a **contract**; do not change during implementation.
{Link to each step’s detailed file. Example structure below.}

- **[Step 0: Prepare and lock plan](./00-setup.md)**: Create and commit protocol artifacts.
- **[Step 1: ...](./01-step-name.md)**: ...
- **[Step 2: ...](./02-step-name.md)**: ...
- ...
- **[Step (last): Finalize](./XX-finalize.md)**:
  * Mark PR Ready
  * Close out work

---

## Protocol Workflow (How to execute)
Follow `High-Level Plan` and this cycle for each step.

- **PROJECT_ROOT**: {absolute path to project root}
- **CWD (worktree)**: {absolute path to worktree}
- **Protocol folder**: {absolute path to .protocols/NNNN-[...]}

All work happens in the worktree (CWD).

### A. Before a new step (restore context)
1. Read `Current Step` from `context.md`.
2. Open the step file (e.g., `01-step-name.md`).
3. Ensure previous changes are committed.

### B. During the step (execute)
1. Do the sub-tasks in the step file.
2. Do **not** change plan files (`plan.md`, `XX-*.md`). They are the contract.
3. Follow Generic Principles below.

### C. After the step (verify & fix)
1. Run checks: `typecheck`, `lint`, `test`. Fix until green.
2. Add a `log.md` entry describing what and why (include commit ID).
3. Rewrite `context.md` for the next step.
4. Verify `main` has no stray files from our branch. Commit with `type(scope): subject [protocol-NNNN/YY]`. Push.
5. Report to the user in the format:
<report_format>
(Protocol, step):

**Done**: what/where/why (also in Log).

**Checks**: which ran (lint/typecheck/test), pass/fail, why.

**Git**: PR link; current branch; commit message; push status; main-branch cleanliness check.

**Working directory**: absolute CWD path.

**Protocol status**: where we are and what’s next.
</report_format>

---

## Generic Principles (MUST follow, shared)
- Balance & simplicity; avoid overengineering.
- No legacy; greenfield decisions allowed.
- Respect coding standards/linters/formatters/JSDoc.
- Keep docs current (Memory Bank), atomic.
- Quality tests: positive/negative/boundaries; reuse helpers.
- Detail & decomposition: plans executable without this chat.

---

## Reference Materials
...
```

#### `context.md` (initial)
```markdown
- **Current Step**: 0
- **Status**: Not Started
- **Last Action Summary**: "Plan generated, awaiting approval."
- **Next Action**: "Start Step 0 (see `00-setup.md`)."
- **Git**: "Branch NNNN-[Task-short-name] created, empty."
- **PROJECT_ROOT**: "{absolute path to project root}"
- **CWD**: "{absolute path to worktree}"
```

#### `log.md` (initial)
```markdown
# Work Log: NNNN — [Short task name]

This is an append-only log:

{add entries about actions, decisions, gotchas, solved issues}
```

#### `00-setup.md` template
```markdown
# Step 0: Prepare and lock the plan

## Briefing
This is a technical step: commit plan files, publish the branch, and open a PR/MR. These actions must be done before reporting to the user.

## Sub-tasks
1. **Create and save** all protocol artifacts (`plan.md`, `context.md`, `log.md`, `00-setup.md`, and all future step files) in `.protocols/NNNN-[Task-short-name]/`.
2. **Make the first commit** with these files to branch `NNNN-[Task-short-name]`.
3. **Create Draft PR/MR** on GitHub or GitLab.
4. **Update `context.md`**: set `Current Step` to `1`, `Status` to `In Progress`, update `Next Action` for Step 1.
5. **Save** the updated `context.md` **without committing** (it will be in the next step’s commit).
```

#### Step file template (`XX-[step-name].md`)
```markdown
# Step XX: {Step title}

## Briefing
- **Goal:** {short goal}
- **Key files:**
  - `src/...`
- **Additional info:** {important details}

## Sub-tasks
{Detailed steps, paths relative to PROJECT_ROOT}

## Workflow
1. Execute sub-tasks.
2. Verify: run `lint`, `typecheck`, `test` (scope as needed). Fix failures.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions).
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-NNNN/XX]"`. Push.
5. Report to user using the step report format above.
```
