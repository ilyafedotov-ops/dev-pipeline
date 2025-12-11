You are an AI agent resuming paused work. Safely restore context, analyze project state, and prepare for the next step.

Follow Generic Principles from `protocol-new.prompt.md` (balance, no legacy, tests, detail).

## Required inputs
- Protocol number: `{PROTOCOL_NUMBER}`
- Protocol name: `NNNN-[Task-short-name]`
- Base branch: `main` (confirm if different)
- CI target: GitHub / GitLab / both

**Provided:**
* Protocol number = `{PROTOCOL_NUMBER}`

**Self-diagnostic algorithm:**

### Phase 1: Locate and gather data

1. **Find your workspace:**
   * Derive full protocol name from number (`NNNN-[Task-short-name]`) by reading `../worktrees/`.
   * **cd into `../worktrees/NNNN-[Task-short-name]`** — this is your CWD for all commands.

2. **Read the “official” status:**
   * Open `.protocols/NNNN-[Task-short-name]/context.md`. Note `Current Step`.

3. **Check the “recorded” status:**
   * Run `git log -1 --pretty=format:"%s"` and find the last step from `[protocol-NNNN/XX]`.

4. **Check the “current” state:**
   * Run `git status --porcelain`. Any uncommitted changes?
   * Run `git fetch origin` and compare `main` vs `origin/main`. If behind, **stop and ask the user about updating.**
   * If required checks exist (`typecheck`, `lint`), run them. On failure, **stop and report**.

### Phase 2: Analyze and decide

Compare the data. Three scenarios:

**A: Clean state (most common)**
- Condition: `git status` empty and last commit tag equals `(Current Step - 1)`.
- Action: You’re ready; go to Phase 3.

**B: Interrupted mid-step**
- Condition: `git status` shows uncommitted changes.
- Action:
  1) Tell user: "Found unfinished changes for step `[Current Step]`."
  2) Say: "Reviewing changes and continuing." Inspect what’s done vs pending; proceed to Phase 3 to continue the step.

**C: Commit done, protocol not updated**
- Condition: `git status` empty, but last commit tag **equals** `Current Step`.
- Action:
  1) Tell user: "Desync detected. Step `[Current Step]` committed, protocol not updated. Correcting."
  2) Do missing post-step tasks:
     * Add `log.md` entry based on last commit (`git log -1`).
     * Rewrite `context.md`: bump `Current Step`, set `Status`, `Last Action Summary`, `Next Action` for the **next** step.
  3) Now you’re clean; continue with current step.

### Phase 3: Prepare to work

1. **Mark context restoration:**
   * Open `.protocols/NNNN-[Task-short-name]/log.md`.
   * Count `Restore context` entries. Add new entry after the header: `Restore context: protocol-NNNN#ctx-[new_number]`.

2. **Read the next step:**
   * From updated `context.md`, note `Current Step` and `Next Action`.
   * Open the step file (e.g., `.protocols/NNNN-[Task-short-name]/03-implement-feature.md`). Study it carefully; it’s the only source.

3. **Verify environment:**
   * Ensure CWD is the correct worktree `NNNN-[Task-short-name]`. If not, report error.
   * Ensure you’re on the correct git branch.

### Phase 4: Final report

Report readiness to the user.

Example (Scenario B):
> "Context restored for protocol `NNNN-[Task-short-name]`. Found unfinished changes for step `03`, reviewed them, ready to continue.
>
> **CWD:** {absolute worktree path}
> **Main branch state:** {confirm main vs origin/main; no stray files}
> **Current state:** Ready to continue **step 03**
> **Next task:** {short description from step file}
"

Work starts only after user confirmation.
