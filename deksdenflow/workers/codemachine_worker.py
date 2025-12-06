"""
Worker entry point for ingesting CodeMachine workspaces.
"""

from pathlib import Path
from typing import Dict, List, Optional

from deksdenflow.codemachine import (
    AgentSpec,
    CodeMachineConfig,
    ConfigError,
    ModulePolicy,
    config_to_template_payload,
    load_codemachine_config,
    policy_to_dict,
)
from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.logging import get_logger
from deksdenflow.storage import BaseDatabase
from deksdenflow.workers.codex_worker import infer_step_type

log = get_logger(__name__)


def _policies_for_agent(agent: AgentSpec, modules: List[ModulePolicy]) -> List[dict]:
    """
    Attach module policies only when explicitly referenced:
    - trigger modules attach when trigger_agent_id matches the agent id
    - modules attach when the agent references a module_id via raw["moduleId"/"module_id"/"module"] or when the module has
      target_agent_id set to this agent.
    - Multiple matching modules are returned; no global fallback.
    """
    policies: List[dict] = []
    # Prefer explicit module references on agent
    agent_modules = agent.raw.get("moduleId") or agent.raw.get("module_id") or agent.raw.get("module")
    agent_module_ids = set()
    if isinstance(agent_modules, str):
        agent_module_ids.add(agent_modules)
    elif isinstance(agent_modules, list):
        agent_module_ids.update(str(m) for m in agent_modules)

    for mod in modules:
        target_agent = (mod.target_agent_id or mod.raw.get("targetAgentId") or mod.raw.get("target_agent_id") or "").strip()
        should_attach = False
        if mod.module_id in agent_module_ids:
            should_attach = True
        if target_agent and target_agent == agent.id:
            should_attach = True
        if mod.behavior == "trigger" and mod.trigger_agent_id == agent.id:
            should_attach = True
        if should_attach:
            policies.append(policy_to_dict(mod))
    return policies


def _create_steps_from_config(
    run_id: int,
    cfg: CodeMachineConfig,
    db: BaseDatabase,
) -> int:
    created = 0
    for idx, agent in enumerate(cfg.main_agents):
        step_name = f"{idx:02d}-{agent.id}"
        policies = _policies_for_agent(agent, cfg.modules)
        db.create_step_run(
            protocol_run_id=run_id,
            step_index=idx,
            step_name=step_name,
            step_type=infer_step_type(step_name),
            status=StepStatus.PENDING,
            model=agent.model,
            engine_id=agent.engine_id,
            policy=policies,
            summary=agent.description,
        )
        created += 1
    return created


def import_codemachine_workspace(
    project_id: int,
    protocol_run_id: int,
    workspace_path: str,
    db: BaseDatabase,
) -> dict:
    """
    Read `.codemachine` config, persist the template graph to the protocol run,
    and materialize step runs from main agents.
    """
    root = Path(workspace_path)
    cfg = load_codemachine_config(root)
    template_payload = config_to_template_payload(cfg)

    db.update_protocol_template(protocol_run_id, template_config=template_payload, template_source=cfg.template)
    created = _create_steps_from_config(protocol_run_id, cfg, db)
    db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
    db.append_event(
        protocol_run_id,
        "codemachine_imported",
        f"Imported CodeMachine workspace with {created} step(s).",
        metadata={
            "workspace": str(root),
            "steps_created": created,
            "template": cfg.template,
        },
    )
    return {"steps_created": created, "workspace": str(root)}


def handle_import_job(payload: dict, db: BaseDatabase) -> None:
    run_id = payload["protocol_run_id"]
    project_id = payload["project_id"]
    workspace = payload["workspace_path"]
    try:
        import_codemachine_workspace(project_id, run_id, workspace, db)
    except ConfigError as exc:
        db.append_event(run_id, "codemachine_import_failed", f"Config error: {exc}")
        db.update_protocol_status(run_id, ProtocolStatus.BLOCKED)
        log.warning("CodeMachine import failed", extra={"protocol_run_id": run_id, "error": str(exc)})
        raise
    except Exception as exc:  # pragma: no cover - best effort
        db.append_event(run_id, "codemachine_import_failed", f"Unexpected error: {exc}")
        db.update_protocol_status(run_id, ProtocolStatus.BLOCKED)
        log.warning("CodeMachine import failed", extra={"protocol_run_id": run_id, "error": str(exc)})
        raise
