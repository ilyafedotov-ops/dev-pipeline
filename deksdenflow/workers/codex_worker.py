"""
Codex worker: resolves protocol context, runs engine-backed planning/exec/QA, and updates DB.
"""

import json
import shutil
from pathlib import Path
from typing import Optional

import deksdenflow.engines_codex  # noqa: F401 - ensure Codex engine is registered

from deksdenflow.codex import run_process, enforce_token_budget, estimate_tokens
from deksdenflow.config import load_config
from deksdenflow.logging import get_logger
from deksdenflow.domain import ProtocolRun, ProtocolStatus, StepRun, StepStatus
from deksdenflow.prompt_utils import prompt_version
from deksdenflow.codemachine.policy_runtime import apply_loop_policies, apply_trigger_policies
from deksdenflow.codemachine.runtime_adapter import (
    build_prompt_text,
    find_agent_for_step,
    is_codemachine_run,
    output_paths,
)
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
from deksdenflow.engines import EngineRequest, registry
from deksdenflow.jobs import RedisQueue
from deksdenflow.spec import (
    PROTOCOL_SPEC_KEY,
    build_spec_from_protocol_files,
    create_steps_from_spec,
    get_step_spec,
    protocol_spec_hash,
    resolve_outputs_map,
    resolve_spec_path,
    update_spec_meta,
    validate_step_spec_paths,
    validate_protocol_spec,
)

log = get_logger(__name__)
MAX_INLINE_TRIGGER_DEPTH = 3


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
    # Inline fallback for dev/local without Redis, or when using fakeredis.
    try:
        target = db.get_step_run(step_run_id)
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


def _resolve_codex_exec_context(step: StepRun, run: ProtocolRun, project, step_spec: Optional[dict] = None) -> tuple[Path, Path, Path, Path, str, Optional[dict], list[str]]:
    """
    Resolve repo/worktree/protocol paths, the prompt text, and outputs config for Codex execution based on step spec.
    """
    step_spec = step_spec or get_step_spec(run.template_config, step.step_name)
    repo_root = Path(project.git_url) if Path(project.git_url).exists() else detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)
    protocol_root = worktree / ".protocols" / run.protocol_name
    plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")

    prompt_ref = step_spec.get("prompt_ref") if step_spec else None
    if prompt_ref:
        step_path = resolve_spec_path(prompt_ref, protocol_root, workspace=worktree)
        if not step_path.exists():
            fallback = (protocol_root / step.step_name).resolve()
            if fallback.exists():
                step_path = fallback
    else:
        step_path = (protocol_root / step.step_name).resolve()
        if not step_path.exists():
            step_path = resolve_spec_path(step.step_name, protocol_root, workspace=worktree)

    step_content = step_path.read_text(encoding="utf-8") if step_path.exists() else ""
    exec_prompt = execute_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_path.name, step_content)
    outputs_cfg = step_spec.get("outputs") if step_spec else None
    # Emit validation info to caller.
    errors = validate_step_spec_paths(protocol_root, step_spec or {}, workspace=worktree)
    return repo_root, worktree, protocol_root, step_path, exec_prompt, outputs_cfg, errors


def _protocol_and_workspace_paths(run: ProtocolRun, project) -> tuple[Path, Path]:
    """
    Best-effort resolution of workspace/protocol roots for prompt resolution
    before a worktree is loaded.
    """
    workspace_root = Path(run.worktree_path or project.git_url or ".").resolve()
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
        spec_hash_val = None
        run = db.get_protocol_run(protocol_run_id)
        if isinstance(run.template_config, dict):
            tmpl_spec = run.template_config.get(PROTOCOL_SPEC_KEY)
            if tmpl_spec:
                spec_hash_val = protocol_spec_hash(tmpl_spec)
        db.append_event(
            protocol_run_id,
            "planned",
            "Protocol planned (stub; codex or repo unavailable).",
            step_run_id=None,
            metadata={"spec_hash": spec_hash_val, "spec_validated": False},
        )
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
    step_spec = get_step_spec(run.template_config, step.step_name)
    spec_hash_val = None
    if isinstance(run.template_config, dict):
        template_spec = run.template_config.get(PROTOCOL_SPEC_KEY)
        if template_spec:
            spec_hash_val = protocol_spec_hash(template_spec)
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
    if is_codemachine_run(run):
        _handle_codemachine_execute(step, run, project, config, db, step_spec=step_spec)
        return
    if shutil.which("codex") is None or not Path(project.git_url).exists():
        db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Executed via stub (codex/repo unavailable)")
        db.append_event(
            step.protocol_run_id,
            "step_completed",
            "Step executed (stub; codex/repo unavailable). QA required.",
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
            handle_quality(step.id, db)
        return
    repo_root, worktree, protocol_root, step_path, exec_prompt, outputs_cfg, spec_errors = _resolve_codex_exec_context(step, run, project, step_spec=step_spec)
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
    exec_model = (
        (step_spec.get("model") if step_spec else None)
        or step.model
        or (project.default_models.get("exec") if project.default_models else None)
        or "codex-5.1-max-xhigh"
    )
    exec_tokens = _budget_and_tokens(exec_prompt, exec_model, "exec", config.token_budget_mode, budget_limit)

    engine_id = (step_spec.get("engine_id") if step_spec else None) or step.engine_id or registry.get_default().metadata.id
    engine = registry.get(engine_id)
    prompt_ver = prompt_version(step_path)
    exec_request = EngineRequest(
        project_id=project.id,
        protocol_run_id=run.id,
        step_run_id=step.id,
        model=exec_model,
        prompt_files=[],
        working_dir=str(worktree),
        extra={
            "prompt_text": exec_prompt,
            "sandbox": "workspace-write",
        },
    )
    exec_result = None
    try:
        exec_result = engine.execute(exec_request)
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
    stdout_text = exec_result.stdout if exec_result and getattr(exec_result, "stdout", None) else ""
    default_protocol_out = (protocol_root / step.step_name).resolve()
    resolved_protocol_out, resolved_aux_outs = resolve_outputs_map(
        outputs_cfg,
        base=protocol_root,
        workspace=worktree,
        default_protocol=default_protocol_out,
        default_aux={},
    )
    resolved_protocol_out.parent.mkdir(parents=True, exist_ok=True)
    if stdout_text:
        resolved_protocol_out.write_text(stdout_text, encoding="utf-8")
        for out_path in resolved_aux_outs.values():
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(stdout_text, encoding="utf-8")

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
        metadata={
            "protocol_run_id": run.id,
            "step_run_id": step.id,
            "estimated_tokens": {"exec": exec_tokens},
            "outputs": {
                "protocol": str(resolved_protocol_out),
                "aux": {k: str(v) for k, v in resolved_aux_outs.items()} if resolved_aux_outs else {},
            },
            "prompt_versions": {"exec": prompt_ver},
            "spec_hash": spec_hash_val,
            "spec_validated": True,
        },
    )
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
    if getattr(config, "auto_qa_after_exec", False):
        db.append_event(
            step.protocol_run_id,
            "qa_enqueued",
            "Auto QA after execution.",
            step_run_id=step.id,
            metadata={"source": "auto_after_exec"},
        )
        handle_quality(step.id, db)


def _handle_codemachine_execute(step: StepRun, run: ProtocolRun, project, config, db: BaseDatabase, step_spec: Optional[dict] = None) -> None:
    workspace = Path(run.worktree_path or project.git_url or ".").resolve()
    codemachine_root = Path(run.protocol_root).resolve() if run.protocol_root else (workspace / ".codemachine")
    template_cfg = run.template_config or {}
    placeholders = template_cfg.get("placeholders") or {}
    spec_hash_val = None
    if isinstance(template_cfg, dict):
        template_spec = template_cfg.get(PROTOCOL_SPEC_KEY)
        if template_spec:
            spec_hash_val = protocol_spec_hash(template_spec)

    agent = find_agent_for_step(step, template_cfg)
    if not agent:
        db.update_step_status(step.id, StepStatus.FAILED, summary="CodeMachine agent not found")
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        db.append_event(
            run.id,
            "codemachine_step_failed",
            f"No agent found for step {step.step_name}",
            step_run_id=step.id,
            metadata={"step_name": step.step_name, "template": template_cfg.get("template")},
        )
        return

    agent_id = str(agent.get("id") or agent.get("agent_id") or step.step_name)
    try:
        prompt_text, prompt_path = build_prompt_text(agent, codemachine_root, placeholders, step_spec=step_spec, workspace=workspace)
    except Exception as exc:  # pragma: no cover - best effort
        db.update_step_status(step.id, StepStatus.FAILED, summary=f"CodeMachine prompt error: {exc}")
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        db.append_event(
            run.id,
            "codemachine_step_failed",
            "Failed to resolve prompt for CodeMachine agent.",
            step_run_id=step.id,
            metadata={"error": str(exc), "agent_id": agent_id, "codemachine_root": str(codemachine_root)},
        )
        return

    cm_prompt_ver = prompt_version(prompt_path)
    engine_defaults = (template_cfg.get("template") or {}).get("engineDefaults") or {}
    engine_id = (
        (step_spec.get("engine_id") if step_spec else None)
        or step.engine_id
        or agent.get("engine_id")
        or engine_defaults.get("execute")
        or registry.get_default().metadata.id
    )
    model = (
        (step_spec.get("model") if step_spec else None)
        or step.model
        or agent.get("model")
        or engine_defaults.get("executeModel")
        or (project.default_models.get("exec") if project.default_models else None)
        or getattr(config, "exec_model", None)
        or registry.get(engine_id).metadata.default_model
        or "codex-5.1-max-xhigh"
    )

    engine = registry.get(engine_id)
    exec_request = EngineRequest(
        project_id=project.id,
        protocol_run_id=run.id,
        step_run_id=step.id,
        model=model,
        prompt_files=[str(prompt_path)],
        working_dir=str(workspace),
        extra={
            "prompt_text": prompt_text,
            "sandbox": "workspace-write",
        },
    )
    db.append_event(
        step.protocol_run_id,
        "codemachine_step_started",
        f"Executing CodeMachine agent {agent_id}.",
        step_run_id=step.id,
        metadata={
            "engine_id": engine_id,
            "model": model,
            "prompt_path": str(prompt_path),
            "prompt_versions": {"exec": cm_prompt_ver},
            "workspace": str(workspace),
            "template": template_cfg.get("template"),
            "spec_hash": spec_hash_val,
        },
    )
    try:
        result = engine.execute(exec_request)
    except Exception as exc:  # pragma: no cover - best effort
        db.update_step_status(step.id, StepStatus.FAILED, summary=f"CodeMachine execution failed: {exc}", engine_id=engine_id, model=model)
        db.append_event(
            step.protocol_run_id,
            "codemachine_step_failed",
            f"Execution failed for agent {agent_id}: {exc}",
            step_run_id=step.id,
            metadata={"engine_id": engine_id, "model": model, "prompt_path": str(prompt_path)},
        )
        loop_decision = apply_loop_policies(step, db, reason="codemachine_exec_failed")
        if loop_decision and loop_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        else:
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        trigger_decision = apply_trigger_policies(step, db, reason="codemachine_exec_failed")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="codemachine_exec_failed",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        return

    output_text = result.stdout or ""
    outputs_cfg = step_spec.get("outputs") if step_spec else None
    default_protocol, default_codemachine = output_paths(workspace, codemachine_root, run, step, agent_id)
    protocol_output_path, aux_outputs = resolve_outputs_map(
        outputs_cfg,
        base=codemachine_root,
        workspace=workspace,
        default_protocol=default_protocol,
        default_aux={"codemachine": default_codemachine},
        prefer_workspace=True,
    )
    protocol_output_path.parent.mkdir(parents=True, exist_ok=True)
    for aux_path in aux_outputs.values():
        aux_path.parent.mkdir(parents=True, exist_ok=True)
    if output_text:
        protocol_output_path.write_text(output_text, encoding="utf-8")
        for aux_path in aux_outputs.values():
            aux_path.write_text(output_text, encoding="utf-8")

    db.update_step_status(
        step.id,
        StepStatus.NEEDS_QA,
        summary=f"Executed CodeMachine agent {agent_id}; pending QA",
        model=model,
        engine_id=engine_id,
    )
    db.append_event(
        step.protocol_run_id,
        "codemachine_step_completed",
        f"CodeMachine agent {agent_id} executed.",
        step_run_id=step.id,
        metadata={
            "engine_id": engine_id,
            "model": model,
            "prompt_path": str(prompt_path),
            "prompt_versions": {"exec": cm_prompt_ver},
            "outputs": {
                "protocol": str(protocol_output_path),
                "aux": {k: str(v) for k, v in aux_outputs.items()} if aux_outputs else {},
            },
            "result_metadata": result.metadata,
            "spec_hash": spec_hash_val,
            "spec_validated": True,
        },
    )

    trigger_decision = apply_trigger_policies(step, db, reason="codemachine_exec_completed")
    if trigger_decision and trigger_decision.get("applied"):
        db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        _enqueue_trigger_target(
            trigger_decision["target_step_id"],
            run.id,
            db,
            source="codemachine_exec_completed",
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
    step_spec = get_step_spec(run.template_config, step.step_name)
    spec_hash_val = None
    if isinstance(run.template_config, dict):
        template_spec = run.template_config.get(PROTOCOL_SPEC_KEY)
        if template_spec:
            spec_hash_val = protocol_spec_hash(template_spec)
    qa_cfg = (step_spec.get("qa") if step_spec else {}) or {}
    qa_policy = qa_cfg.get("policy") if step_spec else None
    if qa_policy == "skip":
        event_type = "qa_skipped_codemachine" if is_codemachine_run(run) else "qa_skipped_policy"
        event_message = "QA skipped (CodeMachine policy)." if event_type == "qa_skipped_codemachine" else "QA skipped by policy."
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA skipped (policy)")
        db.append_event(
            step.protocol_run_id,
            event_type,
            event_message,
            step_run_id=step.id,
            metadata={"policy": qa_policy, "spec_hash": spec_hash_val},
        )
        trigger_decision = apply_trigger_policies(step, db, reason=event_type)
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source=event_type,
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        maybe_complete_protocol(step.protocol_run_id, db)
        return
    workspace_root, protocol_root_hint = _protocol_and_workspace_paths(run, project)
    qa_prompt_path = _resolve_qa_prompt_path(qa_cfg, protocol_root_hint, workspace_root)
    qa_prompt_version = prompt_version(qa_prompt_path)
    if qa_policy is None and is_codemachine_run(run):
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA skipped for CodeMachine run")
        db.append_event(
            step.protocol_run_id,
            "qa_skipped_codemachine",
            "QA skipped (CodeMachine adapter does not run codex QA).",
            step_run_id=step.id,
            metadata={"reason": "codemachine_adapter", "spec_hash": spec_hash_val},
        )
        trigger_decision = apply_trigger_policies(step, db, reason="qa_skipped_codemachine")
        if trigger_decision and trigger_decision.get("applied"):
            db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            _enqueue_trigger_target(
                trigger_decision["target_step_id"],
                run.id,
                db,
                source="qa_skipped_codemachine",
                inline_depth=trigger_decision.get("inline_depth", 0),
            )
        maybe_complete_protocol(step.protocol_run_id, db)
        return
    qa_model = qa_cfg.get("model") or (project.default_models.get("qa", "codex-5.1-max") if project.default_models else "codex-5.1-max")
    qa_engine_id = qa_cfg.get("engine_id") or step.engine_id
    repo_path = workspace_root if workspace_root.exists() else None
    repo_missing = repo_path is None
    repo_not_git = bool(repo_path) and not (repo_path / ".git").exists()
    if shutil.which("codex") is None or (is_codemachine_run(run) and (repo_missing or repo_not_git)) or repo_path is None:
        db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA passed (stub; codex/repo unavailable)")
        metrics.inc_qa_verdict("pass")
        db.append_event(
            step.protocol_run_id,
            "qa_passed",
            "QA passed (stub; codex/repo unavailable).",
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
        return
    repo_root = repo_path or detect_repo_root()
    worktree = load_project(repo_root, run.protocol_name, run.base_branch)
    protocol_root = worktree / ".protocols" / run.protocol_name
    qa_prompt_path = _resolve_qa_prompt_path(qa_cfg, protocol_root, worktree)
    qa_prompt_version = prompt_version(qa_prompt_path)
    qa_prompt = build_prompt(protocol_root, protocol_root / step.step_name)
    qa_tokens = _budget_and_tokens(qa_prompt, qa_model, "qa", config.token_budget_mode, budget_limit)
    try:
        result = run_quality_check(
            protocol_root=protocol_root,
            step_file=protocol_root / step.step_name,
            model=qa_model,
            prompt_file=qa_prompt_path,
            sandbox="read-only",
            max_tokens=budget_limit,
            token_budget_mode=config.token_budget_mode,
            engine_id=qa_engine_id,
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
                    "spec_hash": spec_hash_val,
                },
            )
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
                "QA passed via Codex.",
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
