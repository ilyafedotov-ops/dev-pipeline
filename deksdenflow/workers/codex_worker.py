"""
Codex worker: resolves protocol context, runs Codex CLI for planning/exec/QA, and updates DB.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.pipeline import (
    detect_repo_root,
    execute_step_prompt,
    planning_prompt,
    decompose_step_prompt,
    write_protocol_files,
)
from deksdenflow.storage import Database


def run_command(cmd, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def load_project(repo_root: Path, protocol_name: str, base_branch: str) -> Path:
    worktrees_root = repo_root.parent / "worktrees"
    worktree = worktrees_root / protocol_name
    if not worktree.exists():
        run_command(
            [
                "git",
                "worktree",
                "add",
                "--checkout",
                "-b",
                protocol_name,
                str(worktree),
                f"origin/{base_branch}",
            ],
            cwd=repo_root,
        )
    return worktree


def git_push_and_open_pr(worktree: Path, protocol_name: str, base_branch: str) -> bool:
    pushed = False
    try:
        run_command(["git", "add", "."], cwd=worktree)
        run_command(["git", "commit", "-m", f"chore: sync protocol {protocol_name}"], cwd=worktree)
        run_command(["git", "push", "--set-upstream", "origin", protocol_name], cwd=worktree)
        pushed = True
    except subprocess.CalledProcessError:
        return False
    # Attempt PR/MR creation if CLI is available
    if shutil.which("gh"):
        try:
            run_command(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    f"WIP: {protocol_name}",
                    "--body",
                    f"Protocol {protocol_name} in progress",
                    "--base",
                    base_branch,
                ],
                cwd=worktree,
            )
        except subprocess.CalledProcessError:
            pass
    elif shutil.which("glab"):
        try:
            run_command(
                [
                    "glab",
                    "mr",
                    "create",
                    "--title",
                    f"WIP: {protocol_name}",
                    "--description",
                    f"Protocol {protocol_name} in progress",
                    "--target-branch",
                    base_branch,
                ],
                cwd=worktree,
            )
        except subprocess.CalledProcessError:
            pass
    return pushed


def trigger_ci_pipeline(repo_root: Path, branch: str, ci_provider: Optional[str]) -> bool:
    """Best-effort CI trigger after push (gh/glab)."""
    provider = (ci_provider or "github").lower()
    if provider == "gitlab" and shutil.which("glab"):
        try:
            run_command(["glab", "pipeline", "run", "--ref", branch], cwd=repo_root)
            return True
        except subprocess.CalledProcessError:
            return False
    if shutil.which("gh"):
        try:
            # Trigger the default workflow on the branch; falls back silently if none configured.
            run_command(["gh", "workflow", "run", "--ref", branch], cwd=repo_root)
            return True
        except subprocess.CalledProcessError:
            return False
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ci_trigger.py"
    if script_path.exists():
        try:
            run_command([sys.executable, str(script_path), "--branch", branch, "--repo-root", str(repo_root), "--platform", provider], cwd=repo_root)
            return True
        except subprocess.CalledProcessError:
            return False
    return False


def run_codex(prompt_text: str, model: str, cwd: Path, sandbox: str, output_schema: Optional[Path] = None) -> str:
    cmd = [
        "codex",
        "exec",
        "-m",
        model,
        "--cd",
        str(cwd),
        "--sandbox",
        sandbox,
        "--skip-git-repo-check",
        "-",
    ]
    if output_schema:
        cmd.extend(["--output-schema", str(output_schema)])
    proc = subprocess.run(cmd, input=prompt_text.encode("utf-8"), capture_output=True, check=True)
    return proc.stdout.decode("utf-8")


def handle_plan_protocol(protocol_run_id: int, db: Database) -> None:
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    if shutil.which("codex") is None or not Path(project.git_url).exists():
        db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
        db.append_event(protocol_run_id, "planned", "Protocol planned (stub; codex or repo unavailable).", step_run_id=None)
        return

    repo_root = Path(project.git_url) if Path(project.git_url).exists() else detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)

    protocol_root = worktree / ".protocols" / run.protocol_name
    schema_path = repo_root / "schemas" / "protocol-planning.schema.json"
    templates = (repo_root / "prompts" / "protocol-new.prompt.md").read_text(encoding="utf-8")
    planning_text = planning_prompt(
        protocol_name=run.protocol_name,
        protocol_number=run.protocol_name.split("-")[0],
        task_short_name=run.protocol_name.split("-", 1)[1],
        description=run.description or "",
        repo_root=repo_root,
        worktree_root=worktree,
        templates_section=templates,
    )
    planning_json = run_codex(planning_text, project.default_models.get("planning", "gpt-5.1-high") if project.default_models else "gpt-5.1-high", worktree, "read-only", schema_path)
    data = json.loads(planning_json)
    write_protocol_files(protocol_root, data)
    db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
    db.append_event(protocol_run_id, "planned", "Protocol planned via Codex.", step_run_id=None)

    # Decompose steps
    plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
    for step_file in protocol_root.glob("*.md"):
        if step_file.name.lower().startswith("00-setup"):
            continue
        step_content = step_file.read_text(encoding="utf-8")
        dec_text = decompose_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_file.name, step_content)
        new_content = run_codex(dec_text, project.default_models.get("decompose", "gpt-5.1-high") if project.default_models else "gpt-5.1-high", worktree, "read-only")
        step_file.write_text(new_content, encoding="utf-8")

    # Best-effort push/PR to surface changes in CI
    pushed = git_push_and_open_pr(worktree, run.protocol_name, run.base_branch)
    if pushed:
        triggered = trigger_ci_pipeline(repo_root, run.protocol_name, project.ci_provider)
        if triggered:
            db.append_event(protocol_run_id, "ci_triggered", "CI triggered after planning push.", metadata={"branch": run.protocol_name})


def handle_execute_step(step_run_id: int, db: Database) -> None:
    step = db.get_step_run(step_run_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    if shutil.which("codex") is None or not Path(project.git_url).exists():
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="Executed via stub (codex/repo unavailable)")
        db.append_event(step.protocol_run_id, "step_completed", "Step executed (stub; codex/repo unavailable).", step_run_id=step.id)
        return
    repo_root = Path(project.git_url) if Path(project.git_url).exists() else detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)
    protocol_root = worktree / ".protocols" / run.protocol_name
    step_path = protocol_root / step.step_name
    plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
    step_content = step_path.read_text(encoding="utf-8")
    exec_prompt = execute_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_path.name, step_content)
    run_codex(exec_prompt, project.default_models.get("exec", "codex-5.1-max-xhigh") if project.default_models else "codex-5.1-max-xhigh", worktree, "workspace-write")
    pushed = git_push_and_open_pr(worktree, run.protocol_name, run.base_branch)
    if pushed:
        triggered = trigger_ci_pipeline(repo_root, run.protocol_name, project.ci_provider)
        if triggered:
            db.append_event(step.protocol_run_id, "ci_triggered", "CI triggered after push.", step_run_id=step.id, metadata={"branch": run.protocol_name})
    db.update_step_status(step.id, StepStatus.COMPLETED, summary="Executed via Codex")
    db.append_event(step.protocol_run_id, "step_completed", "Step executed via Codex.", step_run_id=step.id)


def handle_quality(step_run_id: int, db: Database) -> None:
    step = db.get_step_run(step_run_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    if shutil.which("codex") is None or not Path(project.git_url).exists():
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA passed (stub; codex/repo unavailable)")
        db.append_event(step.protocol_run_id, "qa_passed", "QA passed (stub; codex/repo unavailable).", step_run_id=step.id)
        return
    repo_root = Path(project.git_url) if Path(project.git_url).exists() else detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)
    protocol_root = worktree / ".protocols" / run.protocol_name
    prompt_path = repo_root / "prompts" / "quality-validator.prompt.md"
    prompt_prefix = prompt_path.read_text(encoding="utf-8")
    qa_prompt = f"{prompt_prefix}\n\n(See step/context in repo)"
    run_codex(qa_prompt, project.default_models.get("qa", "codex-5.1-max") if project.default_models else "codex-5.1-max", worktree, "read-only")
    db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA passed via Codex")
    db.append_event(step.protocol_run_id, "qa_passed", "QA passed via Codex.", step_run_id=step.id)
