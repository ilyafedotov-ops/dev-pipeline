"""
Codex worker: resolves protocol context, runs engine-backed planning/exec/QA, and updates DB.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import tasksgodzilla.engines_codex  # noqa: F401 - ensure Codex engine is registered

from tasksgodzilla.codex import run_process, enforce_token_budget, estimate_tokens
from tasksgodzilla.config import load_config
from tasksgodzilla.logging import get_logger, log_extra
from tasksgodzilla.domain import ProtocolRun, ProtocolStatus, StepRun, StepStatus
from tasksgodzilla.prompt_utils import prompt_version
from tasksgodzilla.codemachine.policy_runtime import apply_loop_policies, apply_trigger_policies
from tasksgodzilla.codemachine.runtime_adapter import (
    build_prompt_text,
    find_agent_for_step,
    is_codemachine_run,
    output_paths,
)
from tasksgodzilla.pipeline import (
    execute_step_prompt,
    planning_prompt,
    decompose_step_prompt,
    write_protocol_files,
)
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.ci import trigger_ci
from tasksgodzilla.qa import build_prompt, determine_verdict
from tasksgodzilla.workers.state import maybe_complete_protocol
from tasksgodzilla.metrics import metrics
from tasksgodzilla.engines import EngineRequest, registry
from tasksgodzilla.engine_resolver import resolve_prompt_and_outputs
from tasksgodzilla.workers.unified_runner import execute_step_unified, run_qa_unified
from tasksgodzilla.jobs import RedisQueue
from tasksgodzilla.project_setup import auto_clone_enabled, local_repo_dir
from tasksgodzilla.git_utils import create_github_pr, resolve_project_repo_path
from tasksgodzilla.spec import (
    PROTOCOL_SPEC_KEY,
    build_spec_from_protocol_files,
    create_steps_from_spec,
    get_step_spec,
    protocol_spec_hash,
    resolve_spec_path,
    update_spec_meta,
    validate_step_spec_paths,
    validate_protocol_spec,
)

log = get_logger(__name__)
MAX_INLINE_TRIGGER_DEPTH = 3


def _log_context(
    run: Optional[ProtocolRun] = None,
    step: Optional[StepRun] = None,
    job_id: Optional[str] = None,
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
) -> dict:
    """
    Build a standard extra payload so job/protocol/step IDs are always populated.
    """
    return log_extra(
        job_id=job_id,
        project_id=project_id or (run.project_id if run else None),
        protocol_run_id=protocol_run_id or (run.id if run else None),
        step_run_id=step.id if step else None,
    )


def _repo_root_or_block(
    project,
    run: ProtocolRun,
    db: BaseDatabase,
    *,
    job_id: Optional[str] = None,
    clone_if_missing: Optional[bool] = None,
    block_on_missing: bool = True,
) -> Optional[Path]:
    """
    Resolve (and optionally clone) the project repository. Marks the protocol as blocked and
    emits an event when the repo is unavailable.
    """
    try:
        repo_root = resolve_project_repo_path(
            project.git_url,
            project.name,
            project.local_path,
            project_id=project.id,
            clone_if_missing=clone_if_missing,
        )
    except FileNotFoundError as exc:
        db.append_event(
            run.id,
            "repo_missing",
            f"Repository not present locally: {exc}",
            metadata={"git_url": project.git_url},
        )
        if block_on_missing:
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(
            "Repo unavailable",
            extra={
                **_log_context(run=run, job_id=job_id, project_id=project.id),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        db.append_event(
            run.id,
            "repo_clone_failed",
            f"Repository clone failed: {exc}",
            metadata={"git_url": project.git_url},
        )
        if block_on_missing:
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return None
    if not repo_root.exists():
        db.append_event(
            run.id,
            "repo_missing",
            "Repository path not available locally.",
            metadata={"git_url": project.git_url, "resolved_path": str(repo_root)},
        )
        if block_on_missing:
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return None
    return repo_root


def _remote_branch_exists(repo_root: Path, branch: str) -> bool:
    try:
        result = run_process(
            ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _enqueue_trigger_target(
    step_run_id: int,
    protocol_run_id: int,
    db: BaseDatabase,
    source: str,
    inline_depth: int = 0,
) -> Optional[dict]:
    """
    Enqueue a triggered step for execution. If Redis is unavailable, fall back
    to synchronous inline execution to mirror CodeMachine's immediate trigger behavior.
    """
    config = load_config()
    if inline_depth >= MAX_INLINE_TRIGGER_DEPTH:
        db.append_event(
            protocol_run_id,
            "trigger_inline_depth_exceeded",
            f"Inline trigger depth exceeded ({inline_depth}/{MAX_INLINE_TRIGGER_DEPTH}).",
            step_run_id=step_run_id,
            metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
        )
        return None
    queue = None
    force_inline = False
    if config.redis_url:
        try:
            queue = RedisQueue(config.redis_url)
            force_inline = getattr(queue, "_is_fakeredis", False)
            if not force_inline:
                job = queue.enqueue("execute_step_job", {"step_run_id": step_run_id})
                db.append_event(
                    protocol_run_id,
                    "trigger_enqueued",
                    "Triggered step enqueued for execution.",
                    step_run_id=step_run_id,
                    metadata={"job_id": job.job_id, "target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
                )
                return job.asdict()
        except Exception as exc:  # pragma: no cover - best effort
            db.append_event(
                protocol_run_id,
                "trigger_enqueue_failed",
                f"Failed to enqueue triggered step: {exc}",
                step_run_id=step_run_id,
                metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
            )
            return None
    target: Optional[StepRun] = None
    target_qa_skip = False
    try:
        target = db.get_step_run(step_run_id)
        try:
            run = db.get_protocol_run(protocol_run_id)
            target_spec = get_step_spec(run.template_config, target.step_name) or {}
            target_qa_skip = (target_spec.get("qa") or {}).get("policy") == "skip"
        except Exception:
            target_qa_skip = False
    except Exception:
        target = None
    if (queue is None or force_inline) and target_qa_skip:
        db.append_event(
            protocol_run_id,
            "trigger_pending",
            "Triggered step pending; no queue configured.",
            step_run_id=step_run_id,
            metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
        )
        return None
    # Inline fallback for dev/local without Redis, or when using fakeredis.
    try:
        target = target or db.get_step_run(step_run_id)
        merged_state = dict(target.runtime_state or {})
        merged_state["inline_trigger_depth"] = inline_depth
        db.update_step_status(step_run_id, StepStatus.RUNNING, summary="Triggered (inline)", runtime_state=merged_state)
        db.append_event(
            protocol_run_id,
            "trigger_executed_inline",
            "Triggered step executed inline (no queue configured or fakeredis).",
            step_run_id=step_run_id,
            metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
        )
        handle_execute_step(step_run_id, db)
        return {"inline": True, "target_step_id": step_run_id}
    except Exception as exc:  # pragma: no cover - best effort
        db.append_event(
            protocol_run_id,
            "trigger_inline_failed",
            f"Inline trigger failed: {exc}",
            step_run_id=step_run_id,
            metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
        )
        try:
            db.update_step_status(step_run_id, StepStatus.FAILED, summary=f"Trigger inline failed: {exc}")
        except Exception:
            pass
        return None


def _budget_and_tokens(prompt_text: str, model: str, phase: str, token_budget_mode: str, max_tokens: Optional[int]) -> int:
    """
    Enforce configured token budgets and record estimated usage for observability.
    Returns the estimated token count for the prompt.
    """
    enforce_token_budget(prompt_text, max_tokens, phase, mode=token_budget_mode)
    estimated = estimate_tokens(prompt_text)
    metrics.observe_tokens(phase, model, estimated)
    return estimated


def _protocol_and_workspace_paths(run: ProtocolRun, project) -> tuple[Path, Path]:
    """
    Best-effort resolution of workspace/protocol roots for prompt resolution
    before a worktree is loaded.
    """
    if run.worktree_path:
        workspace_base = Path(run.worktree_path).expanduser()
    elif project.local_path and Path(project.local_path).expanduser().exists():
        workspace_base = Path(project.local_path).expanduser()
    else:
        workspace_base = local_repo_dir(project.git_url, project.name, project_id=project.id)
    workspace_root = workspace_base.resolve()
    protocol_root = Path(run.protocol_root).resolve() if run.protocol_root else (workspace_root / ".protocols" / run.protocol_name)
    return workspace_root, protocol_root


def _resolve_qa_prompt_path(qa_cfg: dict, protocol_root: Path, workspace: Path) -> Path:
    """
    Resolve the QA prompt path (default or spec-provided) against the protocol
    root and workspace, allowing prompts outside `.protocols/`.
    """
    prompt_ref = qa_cfg.get("prompt") if isinstance(qa_cfg, dict) else None
    if prompt_ref:
        return resolve_spec_path(str(prompt_ref), protocol_root, workspace=workspace)
    return (workspace / "prompts" / "quality-validator.prompt.md").resolve()


def _resolve_step_path_for_qa(protocol_root: Path, step_name: str, workspace: Path) -> Path:
    """
    Resolve a step path for QA purposes, falling back to spec path resolution.
    """
    step_path = (protocol_root / step_name).resolve()
    if step_path.exists():
        return step_path
    alt = (protocol_root / f"{step_name}.md").resolve()
    if alt.exists():
        return alt
    return resolve_spec_path(step_name, protocol_root, workspace=workspace)


def _append_protocol_log(protocol_root: Path, message: str) -> None:
    """
    Best-effort log.md appender for automatic state notes.
    """
    log_path = protocol_root / "log.md"
    try:
        if not log_path.exists():
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        entry = f"- {timestamp} - {message}\n"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    except Exception:
        return


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
    run = db.get_protocol_run(protocol_run_id)
    template_config = dict(run.template_config or {})
    spec = template_config.get(PROTOCOL_SPEC_KEY)
    if not spec:
        spec = build_spec_from_protocol_files(protocol_root)
        template_config[PROTOCOL_SPEC_KEY] = spec
        db.update_protocol_template(protocol_run_id, template_config, run.template_source)
    workspace_root = protocol_root.parent.parent if protocol_root.parent.name == ".protocols" else protocol_root.parent
    validation_errors = validate_protocol_spec(protocol_root, spec, workspace=workspace_root)
    if validation_errors:
        for err in validation_errors:
            db.append_event(
                protocol_run_id,
                "spec_validation_error",
                err,
                metadata={"protocol_root": str(protocol_root), "spec_hash": protocol_spec_hash(spec)},
            )
        update_spec_meta(db, protocol_run_id, template_config, run.template_source, status="invalid", errors=validation_errors)
        db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
        return 0
    else:
        update_spec_meta(db, protocol_run_id, template_config, run.template_source, status="valid", errors=[])
    existing = {s.step_name for s in db.list_step_runs(protocol_run_id)}
    return create_steps_from_spec(protocol_run_id, spec, db, existing_names=existing)


def load_project(
    repo_root: Path,
    protocol_name: str,
    base_branch: str,
    *,
    protocol_run_id: Optional[int] = None,
    project_id: Optional[int] = None,
    job_id: Optional[str] = None,
) -> Path:
    worktrees_root = repo_root.parent / "worktrees"
    worktree = worktrees_root / protocol_name
    if not worktree.exists():
        log.info(
            "creating_worktree",
            extra={
                **_log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                "protocol_name": protocol_name,
                "base_branch": base_branch,
            },
        )
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


def _load_project_with_context(
    repo_root: Path,
    protocol_name: str,
    base_branch: str,
    *,
    protocol_run_id: Optional[int] = None,
    project_id: Optional[int] = None,
    job_id: Optional[str] = None,
) -> Path:
    """
    Call `load_project`, but tolerate monkeypatched versions in tests that only
    accept positional args. This preserves logging when our implementation is
    used while keeping compatibility with simple stubs.
    """
    try:
        return load_project(
            repo_root,
            protocol_name,
            base_branch,
            protocol_run_id=protocol_run_id,
            project_id=project_id,
            job_id=job_id,
        )
    except TypeError:
        return load_project(repo_root, protocol_name, base_branch)


def git_push_and_open_pr(
    worktree: Path,
    protocol_name: str,
    base_branch: str,
    *,
    protocol_run_id: Optional[int] = None,
    project_id: Optional[int] = None,
    job_id: Optional[str] = None,
) -> bool:
    pushed = False
    branch_exists = False
    commit_attempted = False
    try:
        run_process(["git", "add", "."], cwd=worktree, capture_output=True, text=True)
        try:
            commit_attempted = True
            run_process(
                ["git", "commit", "-m", f"chore: sync protocol {protocol_name}"],
                cwd=worktree,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            msg = str(exc).lower()
            if "nothing to commit" in msg or "no changes added to commit" in msg or "clean" in msg:
                log.info(
                    "No changes to commit; pushing existing branch state",
                    extra={
                        **_log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                        "protocol_name": protocol_name,
                        "base_branch": base_branch,
                    },
                )
            else:
                raise
        run_process(
            ["git", "push", "--set-upstream", "origin", protocol_name],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
        pushed = True
    except Exception as exc:
        branch_exists = _remote_branch_exists(worktree, protocol_name)
        log.warning(
            "Failed to push branch",
            extra={
                **_log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                "protocol_name": protocol_name,
                "base_branch": base_branch,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "branch_exists": branch_exists,
                "commit_attempted": commit_attempted,
            },
        )
        if not branch_exists:
            try:
                run_process(
                    ["git", "push", "--set-upstream", "origin", protocol_name],
                    cwd=worktree,
                    capture_output=True,
                    text=True,
                )
                return True
            except Exception:
                return False
    # Attempt PR/MR creation if CLI is available
    pr_title = f"WIP: {protocol_name}"
    pr_body = f"Protocol {protocol_name} in progress"
    if shutil.which("gh"):
        try:
            run_process(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    pr_title,
                    "--body",
                    pr_body,
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
                    pr_title,
                    "--description",
                    pr_body,
                    "--target-branch",
                    base_branch,
                ],
                cwd=worktree,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
    else:
        if create_github_pr(worktree, head=protocol_name, base=base_branch, title=pr_title, body=pr_body):
            pushed = True
    return pushed or branch_exists


def trigger_ci_pipeline(
    repo_root: Path,
    branch: str,
    ci_provider: Optional[str],
    *,
    protocol_run_id: Optional[int] = None,
    project_id: Optional[int] = None,
    job_id: Optional[str] = None,
) -> bool:
    """Best-effort CI trigger after push (gh/glab)."""
    provider = (ci_provider or "github").lower()
    result = trigger_ci(provider, repo_root, branch)
    log.info(
        "CI trigger",
        extra={
            **_log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
            "provider": provider,
            "branch": branch,
            "triggered": result,
        },
    )
    return result


def handle_plan_protocol(protocol_run_id: int, db: BaseDatabase, job_id: Optional[str] = None) -> None:
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    config = load_config()
    planning_prompt_path = None
    log.info(
        "Planning protocol",
        extra={
            **_log_context(run=run, job_id=job_id),
            "protocol_name": run.protocol_name,
            "branch": run.protocol_name,
        },
    )
    if shutil.which("codex") is None:
        workspace_root, protocol_root = _protocol_and_workspace_paths(run, project)
        db.update_protocol_paths(protocol_run_id, str(workspace_root), str(protocol_root))
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text(f"# Plan for {run.protocol_name}\n\n- [ ] Execute demo step\n", encoding="utf-8")
        (protocol_root / "context.md").write_text(run.description or "Auto-generated stub context.", encoding="utf-8")
        (protocol_root / "log.md").write_text("", encoding="utf-8")
        setup_file = protocol_root / "00-setup.md"
        work_file = protocol_root / "01-demo.md"
        if not setup_file.exists():
            setup_file.write_text("Prepare workspace and dependencies.", encoding="utf-8")
        if not work_file.exists():
            work_file.write_text("Implement the demo task.", encoding="utf-8")

        template_cfg = dict(run.template_config or {})
        spec = template_cfg.get(PROTOCOL_SPEC_KEY)
        if not spec:
            spec = build_spec_from_protocol_files(protocol_root, default_qa_policy="skip")
            template_cfg[PROTOCOL_SPEC_KEY] = spec
            db.update_protocol_template(protocol_run_id, template_cfg, run.template_source)
        spec_hash_val = protocol_spec_hash(spec) if spec else None
        create_steps_from_spec(protocol_run_id, spec, db, existing_names={s.step_name for s in db.list_step_runs(protocol_run_id)})
        update_spec_meta(db, protocol_run_id, template_cfg, run.template_source, status="valid", errors=[])
        db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
        db.append_event(
            protocol_run_id,
            "planned",
            "Protocol planned (stub; codex unavailable).",
            step_run_id=None,
            metadata={"spec_hash": spec_hash_val, "spec_validated": True},
        )
        return

    repo_root = _repo_root_or_block(project, run, db, job_id=job_id)
    if repo_root is None:
        return

    worktree = _load_project_with_context(
        repo_root,
        run.protocol_name,
        run.base_branch,
        protocol_run_id=run.id,
        project_id=project.id,
        job_id=job_id,
    )

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

    engine = registry.get_default()
    planning_request = EngineRequest(
        project_id=project.id,
        protocol_run_id=run.id,
        step_run_id=0,
        model=planning_model,
        prompt_files=[],
        working_dir=str(worktree),
        extra={
            "prompt_text": planning_text,
            "sandbox": "read-only",
            "output_schema": str(schema_path),
        },
    )
    planning_result = engine.plan(planning_request)
    planning_json = planning_result.stdout
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
        dec_text = decompose_step_prompt(
            run.protocol_name,
            run.protocol_name.split("-")[0],
            plan_md,
            step_file.name,
            step_content,
        )
        decompose_tokens += _budget_and_tokens(dec_text, decompose_model, "decompose", config.token_budget_mode, budget_limit)

        decompose_request = EngineRequest(
            project_id=project.id,
            protocol_run_id=run.id,
            step_run_id=0,
            model=decompose_model,
            prompt_files=[],
            working_dir=str(worktree),
            extra={
                "prompt_text": dec_text,
                "sandbox": "read-only",
            },
        )
        decompose_result = engine.plan(decompose_request)
        new_content = decompose_result.stdout
        step_file.write_text(new_content, encoding="utf-8")

    db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
    run = db.get_protocol_run(run.id)
    spec = (run.template_config or {}).get(PROTOCOL_SPEC_KEY)
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
            "spec_hash": protocol_spec_hash(spec) if spec else None,
            "spec_validated": True,
        },
    )

    # Best-effort push/PR to surface changes in CI
    pushed = git_push_and_open_pr(
        worktree,
        run.protocol_name,
        run.base_branch,
        protocol_run_id=run.id,
        project_id=project.id,
        job_id=job_id,
    )
    if pushed:
        triggered = trigger_ci_pipeline(
            repo_root,
            run.protocol_name,
            project.ci_provider,
            protocol_run_id=run.id,
            project_id=project.id,
            job_id=job_id,
        )
        if triggered:
            db.append_event(protocol_run_id, "ci_triggered", "CI triggered after planning push.", metadata={"branch": run.protocol_name})


def handle_execute_step(step_run_id: int, db: BaseDatabase, job_id: Optional[str] = None) -> None:
    step = db.get_step_run(step_run_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    config = load_config()
    auto_clone = auto_clone_enabled()
    budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
    step_spec = get_step_spec(run.template_config, step.step_name)
    qa_cfg = (step_spec.get("qa") if step_spec else {}) or {}
    qa_policy = qa_cfg.get("policy")
    template_cfg = run.template_config or {}
    protocol_spec = template_cfg.get(PROTOCOL_SPEC_KEY) if isinstance(template_cfg, dict) else None
    spec_hash_val = protocol_spec_hash(protocol_spec) if protocol_spec else None
    log.info(
        "Executing step",
        extra={
            **_log_context(run=run, step=step, job_id=job_id),
            "protocol_name": run.protocol_name,
            "branch": run.protocol_name,
            "step_name": step.step_name,
        },
    )
    db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
    codemachine = is_codemachine_run(run)
    step_path: Optional[Path] = None
    repo_root: Optional[Path] = None

    def _stub_execute(reason: str) -> None:
        summary = f"Executed via stub ({reason})"
        if qa_policy == "skip":
            db.update_step_status(step.id, StepStatus.COMPLETED, summary=summary)
            db.append_event(
                step.protocol_run_id,
                "step_completed",
                f"Step executed (stub; {reason}). QA skipped by policy.",
                step_run_id=step.id,
                metadata={"spec_hash": spec_hash_val},
            )
            db.append_event(
                step.protocol_run_id,
                "qa_skipped_policy",
                "QA skipped by policy during stub execution.",
                step_run_id=step.id,
                metadata={"policy": qa_policy, "spec_hash": spec_hash_val},
            )
            trigger_decision = apply_trigger_policies(step, db, reason="qa_skipped_policy")
            if trigger_decision and trigger_decision.get("applied"):
                db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
                _enqueue_trigger_target(
                    trigger_decision["target_step_id"],
                    run.id,
                    db,
                    source="qa_skipped_policy",
                    inline_depth=trigger_decision.get("inline_depth", 0),
                )
            maybe_complete_protocol(step.protocol_run_id, db)
            return
        db.update_step_status(step.id, StepStatus.NEEDS_QA, summary=summary)
        db.append_event(
            step.protocol_run_id,
            "step_completed",
            f"Step executed (stub; {reason}). QA required.",
            step_run_id=step.id,
            metadata={"spec_hash": spec_hash_val},
        )
        trigger_decision = apply_trigger_policies(step, db, reason="exec_stub")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="exec_stub",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        if getattr(config, "auto_qa_after_exec", False):
            db.append_event(
                step.protocol_run_id,
                "qa_enqueued",
                "Auto QA after execution.",
                step_run_id=step.id,
                metadata={"source": "auto_after_exec"},
            )
            handle_quality(step.id, db, job_id=job_id)

    if codemachine:
        repo_root = _repo_root_or_block(project, run, db, job_id=job_id)
        if repo_root is None:
            db.update_step_status(step.id, StepStatus.BLOCKED, summary="Repository unavailable")
            return
    else:
        repo_root = _repo_root_or_block(
            project,
            run,
            db,
            job_id=job_id,
            block_on_missing=False,
            clone_if_missing=auto_clone,
        )
        if repo_root is None:
            _stub_execute("repository unavailable")
            return

    if codemachine:
        workspace_root = Path(run.worktree_path).expanduser() if run.worktree_path else repo_root
        protocol_root = Path(run.protocol_root).resolve() if run.protocol_root else (workspace_root / ".codemachine")
    else:
        if shutil.which("codex") is None:
            _stub_execute("codex unavailable")
            return
        worktree = _load_project_with_context(
            repo_root,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=project.id,
            job_id=job_id,
        )
        workspace_root = worktree
        protocol_root = worktree / ".protocols" / run.protocol_name

    spec_errors = validate_step_spec_paths(protocol_root, step_spec or {}, workspace=workspace_root)
    if spec_errors:
        for err in spec_errors:
            db.append_event(
                run.id,
                "spec_validation_error",
                err,
                step_run_id=step.id,
                metadata={"step": step.step_name, "spec_hash": spec_hash_val},
            )
        db.update_step_status(step.id, StepStatus.FAILED, summary="Spec validation failed")
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return

    resolution = resolve_prompt_and_outputs(
        step_spec or {},
        protocol_root=protocol_root,
        workspace_root=workspace_root,
        protocol_spec=protocol_spec,
        default_engine_id=step.engine_id or registry.get_default().metadata.id,
    )
    kind = "codemachine" if codemachine else "codex"
    engine_id = resolution.engine_id or registry.get_default().metadata.id
    exec_model: Optional[str] = resolution.model

    if codemachine:
        agent = find_agent_for_step(step, template_cfg)
        if not agent:
            db.update_step_status(step.id, StepStatus.FAILED, summary="CodeMachine agent not found")
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            db.append_event(
                run.id,
                "codemachine_step_failed",
                "CodeMachine agent not found.",
                step_run_id=step.id,
                metadata={"step_name": step.step_name, "template": template_cfg.get("template")},
            )
            return
        placeholders = template_cfg.get("placeholders") or {}
        prompt_text, prompt_path = build_prompt_text(agent, protocol_root, placeholders, step_spec=step_spec, workspace=workspace_root)
        engine_defaults = (template_cfg.get("template") or {}).get("engineDefaults") or {}
        agent_id = str(agent.get("id") or agent.get("agent_id") or step.step_name)
        engine_id = (
            step_spec.get("engine_id")
            or step.engine_id
            or agent.get("engine_id")
            or engine_defaults.get("execute")
            or registry.get_default().metadata.id
        )
        exec_model = (
            exec_model
            or step_spec.get("model")
            or step.model
            or agent.get("model")
            or engine_defaults.get("executeModel")
            or (project.default_models.get("exec") if project.default_models else None)
            or getattr(config, "exec_model", None)
            or registry.get(engine_id).metadata.default_model
            or "codex-5.1-max-xhigh"
        )
        resolution.prompt_path = prompt_path
        resolution.prompt_text = prompt_text
        resolution.prompt_version = prompt_version(prompt_path)
        resolution.engine_id = engine_id
        resolution.model = exec_model
        resolution.agent_id = agent_id
        resolution.step_name = step.step_name
        default_protocol, default_codemachine = output_paths(workspace_root, protocol_root, run, step, agent_id)
        if not resolution.outputs.protocol:
            resolution.outputs.protocol = default_protocol
            resolution.outputs.raw["protocol"] = str(default_protocol)
        if "codemachine" not in resolution.outputs.aux:
            resolution.outputs.aux["codemachine"] = default_codemachine
        resolution.workdir = workspace_root
        step_path = resolution.prompt_path
    else:
        step_path = resolution.prompt_path
        if not step_path.exists():
            fallback = (protocol_root / step.step_name).resolve()
            if fallback.exists():
                step_path = fallback
        step_content = step_path.read_text(encoding="utf-8") if step_path.exists() else ""
        plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
        exec_prompt = execute_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_path.name, step_content)
        engine_id = step_spec.get("engine_id") or step.engine_id or engine_id
        exec_model = (
            exec_model
            or step_spec.get("model")
            or step.model
            or (project.default_models.get("exec") if project.default_models else None)
            or "codex-5.1-max-xhigh"
        )
        resolution.prompt_path = step_path
        resolution.prompt_text = exec_prompt
        resolution.prompt_version = prompt_version(step_path)
        resolution.engine_id = engine_id
        resolution.model = exec_model
        resolution.workdir = workspace_root
        if not resolution.outputs.protocol:
            default_protocol_out = step_path if step_path else (protocol_root / step.step_name).resolve()
            resolution.outputs.protocol = default_protocol_out
            resolution.outputs.raw["protocol"] = str(default_protocol_out)

    try:
        engine = registry.get(engine_id)
    except KeyError as exc:  # pragma: no cover - defensive guard
        db.update_step_status(step.id, StepStatus.FAILED, summary=str(exc))
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        db.append_event(
            run.id,
            "step_execution_failed",
            f"Execution failed: {exc}",
            step_run_id=step.id,
            metadata={"engine_id": engine_id, "spec_hash": spec_hash_val},
        )
        return

    if engine.metadata.id == "codex" and shutil.which("codex") is None:
        _stub_execute("codex unavailable")
        return

    exec_tokens = _budget_and_tokens(resolution.prompt_text, exec_model, "exec", config.token_budget_mode, budget_limit)
    db.append_event(
        step.protocol_run_id,
        "step_started",
        f"Executing step via {kind.title()}.",
        step_run_id=step.id,
        metadata={
            "engine_id": engine_id,
            "model": exec_model,
            "prompt_path": str(resolution.prompt_path),
            "prompt_versions": {"exec": resolution.prompt_version},
            "spec_hash": spec_hash_val,
            "agent_id": resolution.agent_id,
        },
    )
    try:
        exec_result = execute_step_unified(
            resolution,
            project_id=project.id,
            protocol_run_id=run.id,
            step_run_id=step.id,
        )
    except Exception as exc:  # pragma: no cover - best effort
        db.update_step_status(step.id, StepStatus.FAILED, summary=f"Execution error: {exc}")
        db.append_event(
            step.protocol_run_id,
            "step_execution_failed",
            f"Execution failed: {exc}",
            step_run_id=step.id,
            metadata={"protocol_run_id": run.id, "step_run_id": step.id, "model": exec_model},
        )
        loop_decision = apply_loop_policies(step, db, reason="exec_failed")
        if loop_decision and loop_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        trigger_decision = apply_trigger_policies(step, db, reason="exec_failed")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="exec_failed",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        else:
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return

    if kind == "codex":
        pushed = git_push_and_open_pr(
            workspace_root,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=project.id,
            job_id=job_id,
        )
        if pushed:
            triggered = trigger_ci_pipeline(
                workspace_root,
                run.protocol_name,
                project.ci_provider,
                protocol_run_id=run.id,
                project_id=project.id,
                job_id=job_id,
            )
            if triggered:
                db.append_event(step.protocol_run_id, "ci_triggered", "CI triggered after push.", step_run_id=step.id, metadata={"branch": run.protocol_name})
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        else:
            if _remote_branch_exists(workspace_root, run.protocol_name):
                db.append_event(
                    step.protocol_run_id,
                    "open_pr_branch_exists",
                    "Branch already exists remotely; skipping push/PR.",
                    step_run_id=step.id,
                    metadata={"branch": run.protocol_name},
                )
                db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            else:
                db.append_event(
                    step.protocol_run_id,
                    "open_pr_failed",
                    "Failed to push branch or open PR/MR.",
                    step_run_id=step.id,
                    metadata={"branch": run.protocol_name},
                )
                db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)

    outputs_meta = exec_result.metadata.get("outputs") if exec_result else {}
    base_meta = {
        "protocol_run_id": run.id,
        "step_run_id": step.id,
        "estimated_tokens": {"exec": exec_tokens},
        "outputs": outputs_meta,
        "prompt_versions": {"exec": resolution.prompt_version},
        "prompt_path": str(resolution.prompt_path),
        "engine_id": engine_id,
        "model": exec_model,
        "spec_hash": spec_hash_val,
        "spec_validated": True,
        "agent_id": resolution.agent_id,
    }
    if kind == "codemachine":
        db.append_event(
            step.protocol_run_id,
            "codemachine_step_completed",
            f"CodeMachine agent {resolution.agent_id} executed.",
            step_run_id=step.id,
            metadata=base_meta,
        )
    db.append_event(
        step.protocol_run_id,
        "step_completed",
        f"Step executed via {kind.title()}. {'Inline QA running.' if qa_policy == 'light' else 'QA required.'}",
        step_run_id=step.id,
        metadata=base_meta,
    )
    _append_protocol_log(protocol_root, f"{step.step_name} executed via {kind.title()} ({exec_model or engine_id}); QA {'inline' if qa_policy == 'light' else 'pending'}.")

    trigger_decision = apply_trigger_policies(step, db, reason="exec_completed")
    if trigger_decision and trigger_decision.get("applied"):
        db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        _enqueue_trigger_target(
            trigger_decision["target_step_id"],
            run.id,
            db,
            source="exec_completed",
            inline_depth=trigger_decision.get("inline_depth", 0),
        )

    if qa_policy == "light":
        qa_prompt_path = _resolve_qa_prompt_path(qa_cfg, protocol_root, workspace_root)
        qa_prompt_version = prompt_version(qa_prompt_path)
        step_path_for_qa = _resolve_step_path_for_qa(protocol_root, step.step_name, workspace_root)
        qa_prefix = qa_prompt_path.read_text(encoding="utf-8") if qa_prompt_path.exists() else ""
        qa_body = build_prompt(protocol_root, step_path_for_qa)
        qa_prompt_full = f"{qa_prefix}\\n\\n{qa_body}\\n\\nKeep this QA brief; focus on must-fix issues only."
        qa_model = qa_cfg.get("model") or (project.default_models.get("qa", "codex-5.1-max") if project.default_models else "codex-5.1-max")
        qa_engine_id = qa_cfg.get("engine_id") or step.engine_id or registry.get_default().metadata.id
        try:
            registry.get(qa_engine_id)
        except KeyError as exc:  # pragma: no cover - defensive
            db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Inline QA unavailable; run full QA", model=exec_model, engine_id=engine_id)
            db.append_event(
                step.protocol_run_id,
                "qa_inline_error",
                f"Inline QA unavailable: {exc}",
                step_run_id=step.id,
                metadata={"engine_id": qa_engine_id, "spec_hash": spec_hash_val},
            )
            _append_protocol_log(protocol_root, f"{step.step_name} inline QA unavailable; run full QA.")
            if getattr(config, "auto_qa_after_exec", False):
                handle_quality(step.id, db, job_id=job_id)
            return

        qa_tokens = _budget_and_tokens(qa_prompt_full, qa_model, "qa", config.token_budget_mode, budget_limit)
        try:
            qa_result = run_qa_unified(
                resolution,
                project_id=project.id,
                protocol_run_id=run.id,
                step_run_id=step.id,
                qa_prompt_path=qa_prompt_path,
                qa_prompt_text=qa_prompt_full,
                qa_engine_id=qa_engine_id,
                qa_model=qa_model,
                sandbox="read-only",
            )
            report_text = (
                qa_result.result.stdout.strip()
                if qa_result and qa_result.result and getattr(qa_result.result, "stdout", None)
                else ""
            )
        except Exception as exc:  # pragma: no cover - best effort
            db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Inline QA error; run full QA", model=exec_model, engine_id=engine_id)
            db.append_event(
                step.protocol_run_id,
                "qa_inline_error",
                f"Inline QA failed: {exc}",
                step_run_id=step.id,
                metadata={"engine_id": qa_engine_id, "spec_hash": spec_hash_val},
            )
            _append_protocol_log(protocol_root, f"{step.step_name} inline QA errored; run full QA.")
            if getattr(config, "auto_qa_after_exec", False):
                handle_quality(step.id, db, job_id=job_id)
            return

        report_path = protocol_root / "quality-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        verdict = determine_verdict(report_text).upper()
        qa_meta = {
            **base_meta,
            "estimated_tokens": {"exec": exec_tokens, "qa": qa_tokens},
            "prompt_versions": {"exec": resolution.prompt_version, "qa": qa_prompt_version},
            "qa_engine_id": qa_engine_id,
            "qa_model": qa_model,
        }
        if verdict == "FAIL":
            db.update_step_status(step.id, StepStatus.FAILED, summary="QA verdict: FAIL (inline)", model=exec_model, engine_id=engine_id)
            db.append_event(
                step.protocol_run_id,
                "qa_failed_inline",
                "Inline QA failed.",
                step_run_id=step.id,
                metadata=qa_meta,
            )
            _append_protocol_log(protocol_root, f"{step.step_name} inline QA FAIL ({qa_model}).")
            loop_decision = apply_loop_policies(step, db, reason="qa_failed")
            if loop_decision and loop_decision.get("applied"):
                db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            else:
                db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            metrics.inc_qa_verdict("fail")
        else:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA verdict: PASS (inline)", model=exec_model, engine_id=engine_id)
            db.append_event(
                step.protocol_run_id,
                "qa_passed_inline",
                "Inline QA passed.",
                step_run_id=step.id,
                metadata=qa_meta,
            )
            _append_protocol_log(protocol_root, f"{step.step_name} inline QA PASS ({qa_model}).")
            trigger_decision = apply_trigger_policies(step, db, reason="qa_passed")
            if trigger_decision and trigger_decision.get("applied"):
                db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
                _enqueue_trigger_target(
                    trigger_decision["target_step_id"],
                    run.id,
                    db,
                    source="qa_passed",
                    inline_depth=trigger_decision.get("inline_depth", 0),
                )
            maybe_complete_protocol(step.protocol_run_id, db)
            metrics.inc_qa_verdict("pass")
        return

    db.update_step_status(step.id, StepStatus.NEEDS_QA, summary=f"Executed via {kind.title()}; pending QA", model=exec_model, engine_id=engine_id)
    if getattr(config, "auto_qa_after_exec", False):
        db.append_event(
            step.protocol_run_id,
            "qa_enqueued",
            "Auto QA after execution.",
            step_run_id=step.id,
            metadata={"source": "auto_after_exec"},
        )
        handle_quality(step.id, db, job_id=job_id)




def handle_quality(step_run_id: int, db: BaseDatabase, job_id: Optional[str] = None) -> None:
    step = db.get_step_run(step_run_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    config = load_config()
    auto_clone = auto_clone_enabled()
    budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
    workspace_hint, protocol_hint = _protocol_and_workspace_paths(run, project)
    log.info(
        "Running QA",
        extra={
            **_log_context(run=run, step=step, job_id=job_id),
            "protocol_name": run.protocol_name,
            "branch": run.protocol_name,
            "step_name": step.step_name,
        },
    )
    step_spec = get_step_spec(run.template_config, step.step_name) or {}
    if not step_spec:
        step_spec = {"id": step.step_name, "name": step.step_name, "prompt_ref": step.step_name}
    template_cfg = run.template_config or {}
    protocol_spec = template_cfg.get(PROTOCOL_SPEC_KEY) if isinstance(template_cfg, dict) else None
    spec_hash_val = protocol_spec_hash(protocol_spec) if protocol_spec else None
    qa_cfg = (step_spec.get("qa") if step_spec else {}) or {}
    qa_policy = qa_cfg.get("policy")
    if qa_policy == "skip":
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA skipped (policy)")
        db.append_event(
            step.protocol_run_id,
            "qa_skipped_policy",
            "QA skipped by policy.",
            step_run_id=step.id,
            metadata={"policy": qa_policy, "spec_hash": spec_hash_val},
        )
        _append_protocol_log(protocol_hint, f"{step.step_name} QA skipped by policy.")
        trigger_decision = apply_trigger_policies(step, db, reason="qa_skipped_policy")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="qa_skipped_policy",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        maybe_complete_protocol(step.protocol_run_id, db)
        return

    repo_root = _repo_root_or_block(
        project,
        run,
        db,
        job_id=job_id,
        block_on_missing=auto_clone,
    )
    if repo_root is None:
        db.update_step_status(step.id, StepStatus.BLOCKED, summary="QA blocked; repository unavailable")
        db.append_event(
            step.protocol_run_id,
            "qa_blocked_repo",
            "QA blocked; repository unavailable.",
            step_run_id=step.id,
            metadata={"spec_hash": spec_hash_val},
        )
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return

    if (repo_root / ".git").exists():
        worktree = _load_project_with_context(
            repo_root,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=run.project_id,
            job_id=job_id,
        )
    else:
        worktree = repo_root

    protocol_root = worktree / ".protocols" / run.protocol_name
    qa_prompt_path = _resolve_qa_prompt_path(qa_cfg, protocol_root, worktree)
    qa_prompt_version = prompt_version(qa_prompt_path)
    step_path = _resolve_step_path_for_qa(protocol_root, step.step_name, worktree)

    qa_prefix = qa_prompt_path.read_text(encoding="utf-8") if qa_prompt_path.exists() else ""
    qa_body = build_prompt(protocol_root, step_path)
    qa_prompt_full = f"{qa_prefix}\\n\\n{qa_body}"

    qa_model = qa_cfg.get("model") or (project.default_models.get("qa", "codex-5.1-max") if project.default_models else "codex-5.1-max")
    qa_engine_id = qa_cfg.get("engine_id") or step.engine_id or registry.get_default().metadata.id

    try:
        registry.get(qa_engine_id)
    except KeyError as exc:  # pragma: no cover - defensive guard
        db.update_step_status(step.id, StepStatus.BLOCKED, summary=str(exc))
        db.append_event(
            step.protocol_run_id,
            "qa_error",
            f"QA failed to run: {exc}",
            step_run_id=step.id,
            metadata={"engine_id": qa_engine_id, "spec_hash": spec_hash_val},
        )
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        return

    def _qa_stub(reason: str) -> None:
        db.update_step_status(step.id, StepStatus.COMPLETED, summary=f"QA passed (stub; {reason})")
        metrics.inc_qa_verdict("pass")
        db.append_event(
            step.protocol_run_id,
            "qa_passed",
            f"QA passed (stub; {reason}).",
            step_run_id=step.id,
            metadata={"prompt_versions": {"qa": qa_prompt_version}, "model": qa_model, "spec_hash": spec_hash_val},
        )
        trigger_decision = apply_trigger_policies(step, db, reason="qa_stub_pass")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="qa_stub_pass",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        maybe_complete_protocol(step.protocol_run_id, db)

    if qa_engine_id == "codex" and shutil.which("codex") is None:
        _qa_stub("codex unavailable")
        return

    resolution = resolve_prompt_and_outputs(
        step_spec or {},
        protocol_root=protocol_root,
        workspace_root=worktree,
        protocol_spec=protocol_spec,
        default_engine_id=qa_engine_id,
    )
    qa_tokens = _budget_and_tokens(qa_prompt_full, qa_model, "qa", config.token_budget_mode, budget_limit)

    try:
        qa_result = run_qa_unified(
            resolution,
            project_id=project.id,
            protocol_run_id=run.id,
            step_run_id=step.id,
            qa_prompt_path=qa_prompt_path,
            qa_prompt_text=qa_prompt_full,
            qa_engine_id=qa_engine_id,
            qa_model=qa_model,
            sandbox="read-only",
        )
    except Exception as exc:  # pragma: no cover - best effort
        log.warning(
            "QA job failed",
            extra={
                **_log_context(run=run, step=step, job_id=job_id),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
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
        return
    if not qa_result or not getattr(qa_result, "result", None):
        _qa_stub("qa engine unavailable")
        return

    report_text = qa_result.result.stdout.strip() if getattr(qa_result.result, "stdout", None) else ""
    report_path = protocol_root / "quality-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    verdict = determine_verdict(report_text).upper()

    if verdict == "FAIL":
        db.update_step_status(step.id, StepStatus.FAILED, summary="QA verdict: FAIL")
        db.append_event(
            step.protocol_run_id,
            "qa_failed",
            "QA failed via engine.",
            step_run_id=step.id,
            metadata={
                "protocol_run_id": run.id,
                "step_run_id": step.id,
                "estimated_tokens": {"qa": qa_tokens},
                "prompt_versions": {"qa": qa_prompt_version},
                "model": qa_model,
                "spec_hash": spec_hash_val,
            },
        )
        _append_protocol_log(protocol_root, f"{step.step_name} QA FAIL ({qa_model}).")
        loop_decision = apply_loop_policies(step, db, reason="qa_failed")
        if loop_decision and loop_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        else:
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        metrics.inc_qa_verdict("fail")
    else:
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA verdict: PASS")
        db.append_event(
            step.protocol_run_id,
            "qa_passed",
            "QA passed via engine.",
            step_run_id=step.id,
            metadata={
                "protocol_run_id": run.id,
                "step_run_id": step.id,
                "estimated_tokens": {"qa": qa_tokens},
                "prompt_versions": {"qa": qa_prompt_version},
                "model": qa_model,
                "spec_hash": spec_hash_val,
            },
        )
        _append_protocol_log(protocol_root, f"{step.step_name} QA PASS ({qa_model}).")
        trigger_decision = apply_trigger_policies(step, db, reason="qa_passed")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="qa_passed",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        maybe_complete_protocol(step.protocol_run_id, db)
        metrics.inc_qa_verdict("pass")


def handle_open_pr(protocol_run_id: int, db: BaseDatabase, job_id: Optional[str] = None) -> None:
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    repo_root = _repo_root_or_block(project, run, db, job_id=job_id)
    if not repo_root:
        db.append_event(
            run.id,
            "open_pr_skipped",
            "Repo not available locally; cannot push or open PR/MR.",
            metadata={"git_url": project.git_url},
        )
        return
    try:
        worktree = _load_project_with_context(
            repo_root,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=project.id,
            job_id=job_id,
        )
        pushed = git_push_and_open_pr(
            worktree,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=project.id,
            job_id=job_id,
        )
        if pushed:
            db.append_event(run.id, "open_pr", "Branch pushed and PR/MR requested.", metadata={"branch": run.protocol_name})
            triggered = trigger_ci_pipeline(
                repo_root,
                run.protocol_name,
                project.ci_provider,
                protocol_run_id=run.id,
                project_id=project.id,
                job_id=job_id,
            )
            if triggered:
                db.append_event(
                    run.id,
                    "ci_triggered",
                    "CI triggered after PR/MR request.",
                    metadata={"branch": run.protocol_name},
                )
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        else:
            if _remote_branch_exists(repo_root, run.protocol_name):
                db.append_event(
                    run.id,
                    "open_pr_branch_exists",
                    "Branch already exists remotely; skipping push/PR.",
                    metadata={"branch": run.protocol_name},
                )
                db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            else:
                db.append_event(
                    run.id,
                    "open_pr_failed",
                    "Failed to push branch or open PR/MR.",
                    metadata={"branch": run.protocol_name},
                )
                db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
    except Exception as exc:  # pragma: no cover - best effort
        log.warning(
            "Open PR job failed",
            extra={
                **_log_context(run=run, job_id=job_id),
                "protocol_name": run.protocol_name,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        db.append_event(
            run.id,
            "open_pr_failed",
            f"Open PR/MR failed: {exc}",
            metadata={"branch": run.protocol_name},
        )
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
