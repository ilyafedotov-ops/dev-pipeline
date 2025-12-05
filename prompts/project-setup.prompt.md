You are an engineering agent preparing a repository with the DeksdenFlow_Ilyas_Edition_1.0 starter assets. Use `scripts/project_setup.py` to ensure docs/prompts/CI/schema/pipeline are present. Act safely in an existing repo.

## Inputs to collect/confirm
- Base branch name (default: `main`).
- Whether to init git if missing (`--init-if-needed`).
- Whether a remote `origin` exists (warn, don’t fail).

## Goals
1) Verify git state; initialize if requested.
2) Ensure starter assets exist (docs, prompts, CI configs, schema, pipeline, CI hooks executable).
3) Leave the repo untouched beyond adding missing starter files/placeholders.

## Execution steps
1) **Repo check**
   - Run `git rev-parse --show-toplevel`. If not a git repo and user allows init, run `git init -b <base>`.
   - Run `git remote get-url origin`; if missing, warn the user to add it.
   - Check base branch exists locally (`git show-ref --verify refs/heads/<base>`); warn if missing.
2) **Run setup script**
   - Execute: `python3 scripts/project_setup.py --base-branch <base> [--init-if-needed]`.
   - If Python isn’t available, ask the user for the correct interpreter.
3) **Post-check**
   - List the created/updated paths (docs, prompts, CI configs, schemas, pipeline, CI hooks).
   - Confirm CI scripts are executable.
   - Do **not** commit; user will review first.

## Output to user
- Paths created/confirmed.
- Any warnings (missing origin, missing base branch, placeholder files written).
- Next steps: review placeholders, customize CI commands, and commit. 
