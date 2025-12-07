import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .codex import run_codex_exec, run_command, enforce_token_budget
from .config import load_config
from .logging import get_logger

log = get_logger(__name__)


def prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def slugify(name: str) -> str:
    """Convert a human Task-short-name into a filesystem/branch-safe slug."""
    lower = name.strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]+", "-", lower).strip("-") or "task"


def run(cmd: List[str], cwd: Path) -> None:
    run_command(cmd, cwd=cwd)


def detect_repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def next_protocol_number(repo_root: Path) -> str:
    numbers: List[int] = []
    worktrees_root = repo_root.parent / "worktrees"
    if worktrees_root.is_dir():
        for entry in worktrees_root.iterdir():
            m = re.match(r"^(\d{4})-", entry.name)
            if m:
                numbers.append(int(m.group(1)))
    protocols_root = repo_root / ".protocols"
    if protocols_root.is_dir():
        for entry in protocols_root.iterdir():
            m = re.match(r"^(\d{4})-", entry.name)
            if m:
                numbers.append(int(m.group(1)))
    next_num = (max(numbers) + 1) if numbers else 1
    return f"{next_num:04d}"


def create_worktree(repo_root: Path, protocol_name: str, base_branch: str) -> Path:
    worktrees_root = repo_root.parent / "worktrees"
    worktrees_root.mkdir(parents=True, exist_ok=True)
    worktree_path = worktrees_root / protocol_name
    run(
        [
            "git",
            "worktree",
            "add",
            "--checkout",
            "-b",
            protocol_name,
            str(worktree_path),
            f"origin/{base_branch}",
        ],
        cwd=repo_root,
    )
    log.info(
        "worktree_created",
        extra={"protocol_name": protocol_name, "base_branch": base_branch, "worktree_path": str(worktree_path)},
    )
    return worktree_path


def load_templates(repo_root: Path) -> str:
    protocol_new = repo_root / "prompts" / "protocol-new.prompt.md"
    text = protocol_new.read_text(encoding="utf-8")
    marker = "### TEMPLATES FOR PROTOCOL FILES"
    if marker in text:
        return text.split(marker, 1)[1]
    return text


def planning_prompt(
    protocol_name: str,
    protocol_number: str,
    task_short_name: str,
    description: str,
    repo_root: Path,
    worktree_root: Path,
    templates_section: str,
) -> str:
    return f"""You are a senior planning agent working with TasksGodzilla_Ilyas_Edition_1.0-style protocols.

Your job:
- Create a detailed protocol plan for the task described below.
- Return JSON only (no Markdown fences), matching the schema provided externally by the tool.
- The JSON must have fields: plan_md, context_md, log_md, step_files[].

Context:
- Protocol number: {protocol_number}
- Protocol name: {protocol_name}
- Task short name (Task-short-name): {task_short_name}
- Task description: {description}
- PROJECT_ROOT: {repo_root}
- WORKTREE_ROOT (CWD for work): {worktree_root}

Guidelines:
- Follow the general structure and templates shown below.
- Keep the High-Level Plan as a contract.
- Make steps and sub-steps executable and self-contained.
- Use English; keep paths relative to PROJECT_ROOT.
- Include at least Step 0 (setup) and several numbered steps; end with a finalize step.

You must fill:
- plan_md: full content for plan.md
- context_md: initial content for context.md
- log_md: initial content for log.md
- step_files: array of objects {{ filename, content }} for all step files, including 00-setup.md and XX-*.md.

Do not add any explanation or commentary outside the JSON structure. The tool will validate your response against the given JSON Schema.

Reference templates (for guidance only):
{templates_section}
"""


def decompose_step_prompt(
    protocol_name: str,
    protocol_number: str,
    plan_md: str,
    step_filename: str,
    step_content: str,
) -> str:
    return f"""You are a senior engineering planner.

You receive:
- Protocol {protocol_number} ({protocol_name}) plan.md content.
- A single step file {step_filename}.

Goal:
- Refine and decompose the Sub-tasks in this step into smaller, concrete tasks.
- Preserve the existing headings and overall structure where reasonable.
- Ensure the result is executable, using clear, ordered sub-tasks.

Rules:
- Output only the full updated Markdown content for {step_filename}.
- Do not wrap the result in code fences.
- Keep the plan contract stable; do not contradict plan.md.

plan.md:
----------------
{plan_md}
----------------

Current {step_filename}:
----------------
{step_content}
----------------
"""


def execute_step_prompt(
    protocol_name: str,
    protocol_number: str,
    plan_md: str,
    step_filename: str,
    step_content: str,
) -> str:
    return f"""You are a senior coding agent working inside a TasksGodzilla_Ilyas_Edition_1.0 protocol.

Context:
- Protocol {protocol_number}: {protocol_name}
- plan.md defines the contract for this protocol.
- This step file describes the Sub-tasks you must execute.

Goal for this run:
- Implement all Sub-tasks from {step_filename}.
- Update code, tests, and any referenced files.
- Follow the protocol workflow: run checks, update log/context, commit and push as described in the step file and plan.md.

Rules:
- Work from the current repository root and worktree, following paths in the step file.
- Do not change plan.md or other step contracts.
- Prefer simple, robust solutions with good tests.
- Use English for any new comments or docs.

You must:
1) Read plan.md and {step_filename} to understand the step.
2) Execute all Sub-tasks.
3) Run appropriate checks (lint/typecheck/test/build) as instructed.
4) Update .protocols state files (log.md, context.md) per the workflow.
5) Make a commit and push, using the commit-message format described in the protocol.
6) Finish with a short textual summary of what was done.

plan.md:
----------------
{plan_md}
----------------

Step file {step_filename}:
----------------
{step_content}
----------------
"""


def write_protocol_files(protocol_root: Path, data: Dict[str, object]) -> None:
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text(str(data["plan_md"]), encoding="utf-8")
    (protocol_root / "context.md").write_text(str(data["context_md"]), encoding="utf-8")
    (protocol_root / "log.md").write_text(str(data["log_md"]), encoding="utf-8")
    for step in data["step_files"]:  # type: ignore[index]
        filename = step["filename"]
        content = step["content"]
        target = protocol_root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    log.info("protocol_files_written", extra={"protocol_root": str(protocol_root)})


def open_draft_pr_or_mr(
    worktree_root: Path,
    protocol_root: Path,
    protocol_name: str,
    protocol_number: str,
    task_short_name_slug: str,
    base_branch: str,
    platform: str,
) -> None:
    context = {
        "protocol_name": protocol_name,
        "protocol_number": protocol_number,
        "base_branch": base_branch,
        "platform": platform,
    }
    log.info("commit_protocol_artifacts", extra={**context, "protocol_root": str(protocol_root)})
    run(
        ["git", "add", str(protocol_root)],
        cwd=worktree_root,
    )
    commit_message = (
        f"feat(protocol): add plan for {protocol_name} [protocol-{protocol_number}/00]"
    )
    run(["git", "commit", "-m", commit_message], cwd=worktree_root)

    log.info("push_protocol_branch", extra={**context, "worktree_root": str(worktree_root)})
    run(
        ["git", "push", "--set-upstream", "origin", protocol_name],
        cwd=worktree_root,
    )

    title = f"WIP: {protocol_number} - {task_short_name_slug}"
    body = (
        f"This PR/MR is being worked on according to protocol {protocol_number}.\n"
        f"See protocol directory for the detailed plan: .protocols/{protocol_name}/"
    )

    if platform == "github":
        if shutil.which("gh") is None:
            log.warning("pr_cli_missing", extra={**context, "cli": "gh"})
            return
        log.info("create_draft_pr", extra={**context, "cli": "gh"})
        run(
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--title",
                title,
                "--body",
                body,
                "--base",
                base_branch,
            ],
            cwd=worktree_root,
        )
    elif platform == "gitlab":
        if shutil.which("glab") is None:
            log.warning("pr_cli_missing", extra={**context, "cli": "glab"})
            return
        log.info("create_draft_mr", extra={**context, "cli": "glab"})
        run(
            [
                "glab",
                "mr",
                "create",
                "--draft",
                "--source",
                protocol_name,
                "--target",
                base_branch,
                "--title",
                title,
                "--description",
                body,
            ],
            cwd=worktree_root,
        )
    else:
        log.warning("unknown_pr_platform", extra=context)


def run_pipeline(args) -> None:
    config = load_config()
    repo_root = detect_repo_root()
    log.info("protocol_pipeline_start", extra={"repo_root": str(repo_root)})

    # Use the stricter of per-step or per-protocol budgets when present.
    budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol

    base_branch = args.base_branch or prompt("Base branch to branch from", "main")
    task_short_name_input = args.short_name or prompt(
        "Task short name (Task-short-name, used in NNNN-[Task-short-name])",
        "my-task",
    )
    task_short_name_slug = slugify(task_short_name_input)
    description = args.description or prompt("Task description", "")

    protocol_number = next_protocol_number(repo_root)
    protocol_name = f"{protocol_number}-{task_short_name_slug}"
    context = {
        "protocol_number": protocol_number,
        "protocol_name": protocol_name,
        "base_branch": base_branch,
    }

    log.info(
        "protocol_plan_prepared",
        extra={**context, "description": description},
    )
    confirm = prompt("Proceed with creating worktree and protocol?", "y")
    if confirm.lower() not in ("y", "yes"):
        log.info("protocol_pipeline_aborted", extra={**context, "reason": "user_declined"})
        return

    worktree_root = create_worktree(repo_root, protocol_name, base_branch)
    context["worktree_root"] = str(worktree_root)

    protocol_root = worktree_root / ".protocols" / protocol_name
    context["protocol_root"] = str(protocol_root)
    templates_section = load_templates(repo_root)

    planning_schema = repo_root / "schemas" / "protocol-planning.schema.json"
    if not planning_schema.is_file():
        log.error("planning_schema_not_found", extra={"planning_schema": str(planning_schema), **context})
        sys.exit(1)

    tmp_dir = worktree_root / ".protocols" / protocol_name / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    planning_output = tmp_dir / "planning.json"

    planning_model = args.planning_model or config.planning_model or os.environ.get("PROTOCOL_PLANNING_MODEL", "gpt-5.1-high")
    planning_text = planning_prompt(
        protocol_name=protocol_name,
        protocol_number=protocol_number,
        task_short_name=task_short_name_slug,
        description=description,
        repo_root=repo_root,
        worktree_root=worktree_root,
        templates_section=templates_section,
    )

    enforce_token_budget(planning_text, budget_limit, "planning", mode=config.token_budget_mode)

    log.info("planning_step", extra={**context, "model": planning_model})
    run_codex_exec(
        model=planning_model,
        cwd=worktree_root,
        prompt_text=planning_text,
        sandbox="read-only",
        output_schema=planning_schema,
        output_last_message=planning_output,
    )

    planning_data = json.loads(planning_output.read_text(encoding="utf-8"))
    write_protocol_files(protocol_root, planning_data)
    log.info("protocol_files_ready", extra={**context, "protocol_root": str(protocol_root)})

    plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
    decomposition_model = args.decompose_model or config.decompose_model or os.environ.get("PROTOCOL_DECOMPOSE_MODEL", "gpt-5.1-high")

    for step_file in protocol_root.glob("*.md"):
        if step_file.name.lower().startswith("00-setup"):
            continue
        step_content = step_file.read_text(encoding="utf-8")
        tmp_step = tmp_dir / f"{step_file.name}.decomposed"

        decompose_text = decompose_step_prompt(
            protocol_name=protocol_name,
            protocol_number=protocol_number,
            plan_md=plan_md,
            step_filename=step_file.name,
            step_content=step_content,
        )

        enforce_token_budget(decompose_text, budget_limit, f"decompose:{step_file.name}", mode=config.token_budget_mode)

        log.info("decompose_step", extra={**context, "step_file": step_file.name, "model": decomposition_model})
        run_codex_exec(
            model=decomposition_model,
            cwd=worktree_root,
            prompt_text=decompose_text,
            sandbox="read-only",
            output_last_message=tmp_step,
        )

        new_content = tmp_step.read_text(encoding="utf-8")
        step_file.write_text(new_content, encoding="utf-8")

    # Optionally create Draft PR/MR
    if args.pr_platform:
        log.info("auto_pr_requested", extra={**context, "platform": args.pr_platform})
        open_draft_pr_or_mr(
            worktree_root=worktree_root,
            protocol_root=protocol_root,
            protocol_name=protocol_name,
            protocol_number=protocol_number,
            task_short_name_slug=task_short_name_slug,
            base_branch=base_branch,
            platform=args.pr_platform,
        )

    # Optionally auto-run a specific step
    if args.run_step:
        exec_model = args.exec_model or config.exec_model or os.environ.get("PROTOCOL_EXEC_MODEL", "codex-5.1-max-xhigh")
        step_path = protocol_root / args.run_step
        if not step_path.is_file():
            log.warning("auto_run_step_missing", extra={**context, "step_file": str(step_path)})
        else:
            log.info("auto_run_step", extra={**context, "step_file": str(step_path), "model": exec_model})
            plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
            step_content = step_path.read_text(encoding="utf-8")
            exec_prompt = execute_step_prompt(
                protocol_name=protocol_name,
                protocol_number=protocol_number,
                plan_md=plan_md,
                step_filename=step_path.name,
                step_content=step_content,
            )
            enforce_token_budget(exec_prompt, budget_limit, f"exec:{step_path.name}", mode=config.token_budget_mode)
            run_codex_exec(
                model=exec_model,
                cwd=worktree_root,
                prompt_text=exec_prompt,
                sandbox="workspace-write",
            )

    log.info(
        "protocol_pipeline_complete",
        extra={
            **context,
            "next_steps": [
                "Review plan.md and step files",
                "Commit protocol artifacts and open Draft PR/MR if needed",
                "Execute steps with Codex from the worktree root",
            ],
            "worktree": str(worktree_root),
            "protocol_root": str(protocol_root),
        },
    )
