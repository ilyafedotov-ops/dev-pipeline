"""
Codex worker: resolves protocol context, runs Codex CLI for planning/exec/QA, and updates DB.
"""

import json
import shutil
from pathlib import Path
from typing import Optional

from deksdenflow.codex import run_process, enforce_token_budget, estimate_tokens
from deksdenflow.config import load_config
from deksdenflow.logging import get_logger
from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.prompt_utils import prompt_version
from deksdenflow.pipeline import (
    detect_repo_root,
    execute_step_prompt,
    planning_prompt,
    decompose_step_prompt,
    write_protocol_files,
)
from deksdenflow.storage import BaseDatabase
from deksdenflow.ci import trigger_ci
from deksdenflow.qa import run_quality_check, build_prompt
from deksdenflow.workers.state import maybe_complete_protocol
from deksdenflow.metrics import metrics

log = get_logger(__name__)


def _budget_and_tokens(prompt_text: str, model: str, phase: str, token_budget_mode: str, max_tokens: Optional[int]) -> int:
    """
    Enforce configured token budgets and record estimated usage for observability.
    Returns the estimated token count for the prompt.
    """
    enforce_token_budget(prompt_text, max_tokens, phase, mode=token_budget_mode)
    estimated = estimate_tokens(prompt_text)
    metrics.observe_tokens(phase, model, estimated)
    return estimated


def infer_step_type(filename: str) -> str:
    lower = filename.lower()
    if lower.startswith("00-") or "setup" in lower:
        return "setup"
    if "qa" in lower:
        return "qa"
    return "work"


def sync_step_runs_from_protocol(protocol_root: Path, protocol_run_id: int, db: BaseDatabase) -> int:
    """
    Ensure StepRun rows exist for each step file in the protocol directory.
    """
    step_files = sorted([p for p in protocol_root.glob("*.md") if p.name[0:2].isdigit()])
    existing = {s.step_name: s for s in db.list_step_runs(protocol_run_id)}
    created = 0
    for idx, step_file in enumerate(step_files):
        if step_file.name in existing:
            continue
        db.create_step_run(
            protocol_run_id=protocol_run_id,
            step_index=idx,
            step_name=step_file.name,
            step_type=infer_step_type(step_file.name),
            status=StepStatus.PENDING,
            model=None,
        )
        created += 1
    return created


def load_project(repo_root: Path, protocol_name: str, base_branch: str) -> Path:
    worktrees_root = repo_root.parent / "worktrees"
    worktree = worktrees_root / protocol_name
    if not worktree.exists():
        log.info("Creating worktree", extra={"protocol": protocol_name, "base_branch": base_branch})
        run_process(
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
        run_process(["git", "add", "."], cwd=worktree, capture_output=True, text=True)
        run_process(
            ["git", "commit", "-m", f"chore: sync protocol {protocol_name}"],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
        run_process(
            ["git", "push", "--set-upstream", "origin", protocol_name],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
        pushed = True
    except Exception as exc:
        log.warning("Failed to push branch", extra={"protocol": protocol_name, "error": str(exc)})
        return False
    # Attempt PR/MR creation if CLI is available
    if shutil.which("gh"):
        try:
            run_process(
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
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
    elif shutil.which("glab"):
        try:
            run_process(
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
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
    return pushed


def trigger_ci_pipeline(repo_root: Path, branch: str, ci_provider: Optional[str]) -> bool:
    """Best-effort CI trigger after push (gh/glab)."""
    provider = (ci_provider or "github").lower()
    result = trigger_ci(provider, repo_root, branch)
    log.info("CI trigger", extra={"provider": provider, "branch": branch, "triggered": result})
    return result


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
    proc = run_process(cmd, cwd=cwd, capture_output=True, text=True, input_text=prompt_text)
    return proc.stdout


def handle_plan_protocol(protocol_run_id: int, db: BaseDatabase) -> None:
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    config = load_config()
    planning_prompt_path = None
    log.info(
        "Planning protocol",
        extra={
            "protocol_run_id": run.id,
            "protocol": run.protocol_name,
            "project": project.id,
            "branch": run.protocol_name,
        },
    )
    if shutil.which("codex") is None or not Path(project.git_url).exists():
        db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
        db.append_event(protocol_run_id, "planned", "Protocol planned (stub; codex or repo unavailable).", step_run_id=None)
        return

    repo_root = Path(project.git_url) if Path(project.git_url).exists() else detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)

    budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
    planning_model = project.default_models.get("planning", "gpt-5.1-high") if project.default_models else "gpt-5.1-high"
    protocol_root = worktree / ".protocols" / run.protocol_name
    db.update_protocol_paths(protocol_run_id, str(worktree), str(protocol_root))
    schema_path = repo_root / "schemas" / "protocol-planning.schema.json"
    planning_prompt_path = repo_root / "prompts" / "protocol-new.prompt.md"
    templates = planning_prompt_path.read_text(encoding="utf-8")
    planning_text = planning_prompt(
        protocol_name=run.protocol_name,
        protocol_number=run.protocol_name.split("-")[0],
        task_short_name=run.protocol_name.split("-", 1)[1],
        description=run.description or "",
        repo_root=repo_root,
        worktree_root=worktree,
        templates_section=templates,
    )
    planning_tokens = _budget_and_tokens(planning_text, planning_model, "planning", config.token_budget_mode, budget_limit)
    planning_json = run_codex(
        planning_text,
        planning_model,
        worktree,
        "read-only",
        schema_path,
    )
    data = json.loads(planning_json)
    write_protocol_files(protocol_root, data)
    created_steps = sync_step_runs_from_protocol(protocol_root, protocol_run_id, db)

    # Decompose steps
    plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
    decompose_tokens = 0
    decompose_model = project.default_models.get("decompose", "gpt-5.1-high") if project.default_models else "gpt-5.1-high"
    for step_file in protocol_root.glob("*.md"):
        if step_file.name.lower().startswith("00-setup"):
            continue
        step_content = step_file.read_text(encoding="utf-8")
        dec_text = decompose_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_file.name, step_content)
        decompose_tokens += _budget_and_tokens(dec_text, decompose_model, "decompose", config.token_budget_mode, budget_limit)
        new_content = run_codex(
            dec_text,
            decompose_model,
            worktree,
            "read-only",
        )
        step_file.write_text(new_content, encoding="utf-8")

    db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
    db.append_event(
        protocol_run_id,
        "planned",
        "Protocol planned via Codex.",
        step_run_id=None,
        metadata={
            "steps_created": created_steps,
            "protocol_root": str(protocol_root),
            "models": {"planning": planning_model, "decompose": decompose_model},
            "prompt_versions": {"planning": prompt_version(planning_prompt_path)},
            "estimated_tokens": {"planning": planning_tokens, "decompose": decompose_tokens},
        },
    )

    # Best-effort push/PR to surface changes in CI
    pushed = git_push_and_open_pr(worktree, run.protocol_name, run.base_branch)
    if pushed:
        triggered = trigger_ci_pipeline(repo_root, run.protocol_name, project.ci_provider)
        if triggered:
            db.append_event(protocol_run_id, "ci_triggered", "CI triggered after planning push.", metadata={"branch": run.protocol_name})


def handle_execute_step(step_run_id: int, db: BaseDatabase) -> None:
    step = db.get_step_run(step_run_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    config = load_config()
    budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
    log.info(
        "Executing step",
        extra={
            "step_run_id": step.id,
            "protocol_run_id": run.id,
            "protocol": run.protocol_name,
            "branch": run.protocol_name,
            "step_name": step.step_name,
        },
    )
    db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
    if shutil.which("codex") is None or not Path(project.git_url).exists():
        db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Executed via stub (codex/repo unavailable)")
        db.append_event(
            step.protocol_run_id,
            "step_completed",
            "Step executed (stub; codex/repo unavailable). QA required.",
            step_run_id=step.id,
        )
        if getattr(config, "auto_qa_after_exec", False):
            db.append_event(
                step.protocol_run_id,
                "qa_enqueued",
                "Auto QA after execution.",
                step_run_id=step.id,
                metadata={"source": "auto_after_exec"},
            )
            handle_quality(step.id, db)
        return
    repo_root = Path(project.git_url) if Path(project.git_url).exists() else detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)
    protocol_root = worktree / ".protocols" / run.protocol_name
    step_path = protocol_root / step.step_name
    plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
    step_content = step_path.read_text(encoding="utf-8")
    exec_prompt = execute_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_path.name, step_content)
    exec_model = project.default_models.get("exec", "codex-5.1-max-xhigh") if project.default_models else "codex-5.1-max-xhigh"
    exec_tokens = _budget_and_tokens(exec_prompt, exec_model, "exec", config.token_budget_mode, budget_limit)
    run_codex(
        exec_prompt,
        exec_model,
        worktree,
        "workspace-write",
    )
    pushed = git_push_and_open_pr(worktree, run.protocol_name, run.base_branch)
    if pushed:
        triggered = trigger_ci_pipeline(repo_root, run.protocol_name, project.ci_provider)
        if triggered:
            db.append_event(step.protocol_run_id, "ci_triggered", "CI triggered after push.", step_run_id=step.id, metadata={"branch": run.protocol_name})
    db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Executed via Codex; pending QA")
    db.append_event(
        step.protocol_run_id,
        "step_completed",
        "Step executed via Codex. QA required.",
        step_run_id=step.id,
        metadata={"protocol_run_id": run.id, "step_run_id": step.id, "estimated_tokens": {"exec": exec_tokens}},
    )
    if getattr(config, "auto_qa_after_exec", False):
        db.append_event(
            step.protocol_run_id,
            "qa_enqueued",
            "Auto QA after execution.",
            step_run_id=step.id,
            metadata={"source": "auto_after_exec"},
        )
        handle_quality(step.id, db)


def handle_quality(step_run_id: int, db: BaseDatabase) -> None:
    step = db.get_step_run(step_run_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    config = load_config()
    budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
    log.info(
        "Running QA",
        extra={
            "step_run_id": step.id,
            "protocol_run_id": run.id,
            "protocol": run.protocol_name,
            "branch": run.protocol_name,
            "step_name": step.step_name,
        },
    )
    qa_model = project.default_models.get("qa", "codex-5.1-max") if project.default_models else "codex-5.1-max"
    repo_path = Path(project.git_url) if Path(project.git_url).exists() else None
    prompt_path = (repo_path / "prompts" / "quality-validator.prompt.md") if repo_path else None
    qa_prompt_version = prompt_version(prompt_path)
    if shutil.which("codex") is None or repo_path is None:
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA passed (stub; codex/repo unavailable)")
        metrics.inc_qa_verdict("pass")
        db.append_event(
            step.protocol_run_id,
            "qa_passed",
            "QA passed (stub; codex/repo unavailable).",
            step_run_id=step.id,
            metadata={"prompt_versions": {"qa": qa_prompt_version}, "model": qa_model},
        )
        maybe_complete_protocol(step.protocol_run_id, db)
        return
    repo_root = repo_path or detect_repo_root()
    prompt_path = repo_root / "prompts" / "quality-validator.prompt.md"
    qa_prompt_version = prompt_version(prompt_path)
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)
    protocol_root = worktree / ".protocols" / run.protocol_name
    qa_prompt = build_prompt(protocol_root, protocol_root / step.step_name)
    qa_tokens = _budget_and_tokens(qa_prompt, qa_model, "qa", config.token_budget_mode, budget_limit)
    try:
        result = run_quality_check(
            protocol_root=protocol_root,
            step_file=protocol_root / step.step_name,
            model=qa_model,
            prompt_file=prompt_path,
            sandbox="read-only",
            max_tokens=budget_limit,
            token_budget_mode=config.token_budget_mode,
        )
        verdict = result.verdict.upper()
        if verdict == "FAIL":
            db.update_step_status(step.id, StepStatus.FAILED, summary="QA verdict: FAIL")
            db.append_event(
                step.protocol_run_id,
                "qa_failed",
                "QA failed via Codex.",
                step_run_id=step.id,
                metadata={
                    "protocol_run_id": run.id,
                    "step_run_id": step.id,
                    "estimated_tokens": {"qa": qa_tokens},
                    "prompt_versions": {"qa": qa_prompt_version},
                    "model": qa_model,
                },
            )
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            metrics.inc_qa_verdict("fail")
        else:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA verdict: PASS")
            db.append_event(
                step.protocol_run_id,
                "qa_passed",
                "QA passed via Codex.",
                step_run_id=step.id,
                metadata={
                    "protocol_run_id": run.id,
                    "step_run_id": step.id,
                    "estimated_tokens": {"qa": qa_tokens},
                    "prompt_versions": {"qa": qa_prompt_version},
                    "model": qa_model,
                },
            )
            maybe_complete_protocol(step.protocol_run_id, db)
            metrics.inc_qa_verdict("pass")
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("QA job failed", extra={"step_run_id": step.id, "error": str(exc)})
        db.update_step_status(step.id, StepStatus.FAILED, summary=f"QA error: {exc}")
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        db.append_event(
            step.protocol_run_id,
            "qa_error",
            f"QA failed to run: {exc}",
            step_run_id=step.id,
            metadata={"prompt_versions": {"qa": qa_prompt_version}, "model": qa_model},
        )
        metrics.inc_qa_verdict("fail")


def handle_open_pr(protocol_run_id: int, db: BaseDatabase) -> None:
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    repo_root = Path(project.git_url) if Path(project.git_url).exists() else None
    if not repo_root:
        db.append_event(
            run.id,
            "open_pr_skipped",
            "Repo not available locally; cannot push or open PR/MR.",
            metadata={"git_url": project.git_url},
        )
        return
    try:
        worktree = load_project(repo_root, run.protocol_name, run.base_branch)
        pushed = git_push_and_open_pr(worktree, run.protocol_name, run.base_branch)
        if pushed:
            db.append_event(run.id, "open_pr", "Branch pushed and PR/MR requested.", metadata={"branch": run.protocol_name})
            triggered = trigger_ci_pipeline(repo_root, run.protocol_name, project.ci_provider)
            if triggered:
                db.append_event(
                    run.id,
                    "ci_triggered",
                    "CI triggered after PR/MR request.",
                    metadata={"branch": run.protocol_name},
                )
        else:
            db.append_event(
                run.id,
                "open_pr_failed",
                "Failed to push branch or open PR/MR.",
                metadata={"branch": run.protocol_name},
            )
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("Open PR job failed", extra={"protocol": run.protocol_name, "error": str(exc)})
        db.append_event(
            run.id,
            "open_pr_failed",
            f"Open PR/MR failed: {exc}",
            metadata={"branch": run.protocol_name},
        )
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
