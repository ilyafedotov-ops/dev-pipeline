You are an engineering agent bootstrapping a **new repository** using TasksGodzilla_Ilyas_Edition_1.0. Create the folder structure, prompts, and CI for GitHub Actions and GitLab so the team can start shipping in parallel streams.

## Inputs to confirm with the user
- `PROJECT_NAME`
- `DESCRIPTION`
- Default branch name (assume `main` if not provided)
- Target CI(s): GitHub, GitLab, or both
- Preferred stack hints (Node/Python/Go/etc.) to prefill CI scripts if known

## Goals
1) Create the generic structure and docs
2) Add prompts for new/resume/review workflows
3) Wire CI/CD for GitHub Actions and GitLab (skipping missing CIs if user says so)
4) Keep everything committed to the repo

## Execution checklist

### 0) Safety & repo state
- Confirm you are in the repo root; run `pwd`, `git status -sb`, and `git branch --show-current`.
- If the repo is uninitialized, run `git init -b <default_branch>`.
- Never drop or rewrite user changes.

### 1) Scaffold the structure
- Create directories: `docs/`, `prompts/`, `scripts/ci/`, `.github/workflows/` (if GitHub requested).
- Add `.gitignore` with common ignores (`node_modules`, `dist`, `.venv`, `.env`, `coverage`, `.DS_Store`).
- Add `README.md` describing the project, TasksGodzilla_Ilyas_Edition_1.0 usage, CI entry points, and how to use prompts.
- Add `docs/tasksgodzilla.md` (overview of the 7-step flow) and `docs/ci.md` (how to customize CI scripts).

### 2) Add prompts (as Markdown in `prompts/`)
- `project-init.prompt.md` — this file; keep it updated with the concrete repo name and defaults.
- `protocol-new.prompt.md` — instructions to open a new protocol: branch/worktree creation, plan, PR draft.
- `protocol-resume.prompt.md` — resume a paused protocol safely.
- `protocol-review-merge.prompt.md` — QA/review and merge flow.
- `protocol-review-merge-resume.prompt.md` — resume a paused review.
- Keep links or embedded content from the source gists to stay self-contained.

### 3) CI scripts (in `scripts/ci/`)
- Add executable stubs: `bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh`.
- If the user gave stack hints, prefill the scripts with concrete commands (otherwise leave TODO comments but make them exit 0).

### 4) GitHub Actions (`.github/workflows/ci.yml`)
- Single workflow `CI` triggered on `push` + `pull_request`.
- Steps: checkout → run each CI script if present and executable. Example:
  ```bash
  if [ -x scripts/ci/lint.sh ]; then scripts/ci/lint.sh; else echo "skip lint"; fi
  ```
- Keep the job lean; allow users to add cache later.

### 5) GitLab CI (`.gitlab-ci.yml`)
- Stages: `bootstrap`, `lint`, `typecheck`, `test`, `build`.
- Each job runs the matching `scripts/ci/*.sh` if present; otherwise prints a skip message and exits 0.

### 6) Finalize
- Ensure all new files are added: `git status` then `git add .`.
- Commit with message `chore: scaffold TasksGodzilla_Ilyas_Edition_1.0 starter` (or user-provided format).
- Echo next steps for the user: fill CI scripts, add code, create first protocol using `protocol-new.prompt.md`.

## Constraints
- Default to ASCII; keep instructions concise and explicit.
- Do not run destructive git commands.
- Keep CI passing in an empty repo by allowing missing scripts to skip.

## Deliverable to the user
- A short summary of what was created.
- Paths to the key files (README, docs, prompts, CI configs, scripts).
- Reminder to customize CI scripts with real commands.
