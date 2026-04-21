"""
DevGodzilla Protocol Generation Service

Uses an AI engine (typically `opencode`) to generate `.protocols/<protocol>/` artifacts
inside an isolated worktree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from devgodzilla.engines import EngineNotFoundError, EngineRequest, SandboxMode, get_registry
from devgodzilla.logging import get_logger
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)


@dataclass
class ProtocolGenerationResult:
    success: bool
    engine_id: str
    model: Optional[str]
    worktree_root: Path
    protocol_root: Path
    prompt_path: Path
    created_files: list[Path]
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


def _render_prompt(
    template: str,
    *,
    protocol_name: str,
    description: str,
    step_count: int,
    workflow_context: str = "",
) -> str:
    rendered = (
        template.replace("{{PROTOCOL_NAME}}", protocol_name)
        .replace("{{PROTOCOL_DESCRIPTION}}", description)
        .replace("{{STEP_COUNT}}", str(step_count))
    )
    if "{{WORKFLOW_CONTEXT}}" in rendered:
        rendered = rendered.replace("{{WORKFLOW_CONTEXT}}", workflow_context.strip())
    elif workflow_context.strip():
        rendered = f"{rendered.rstrip()}\n\n{workflow_context.strip()}\n"
    return rendered


class ProtocolGenerationService(Service):
    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)

    def generate(
        self,
        *,
        worktree_root: Path,
        protocol_name: str,
        description: str,
        step_count: int = 3,
        engine_id: str = "opencode",
        model: Optional[str] = None,
        project_id: Optional[int] = None,
        prompt_path: Optional[Path] = None,
        workflow_context: str = "",
        timeout_seconds: int = 900,
        strict_outputs: bool = True,
    ) -> ProtocolGenerationResult:
        worktree_root = worktree_root.expanduser().resolve()
        protocol_root = worktree_root / ".protocols" / protocol_name

        prompt_path = (
            prompt_path.expanduser().resolve()
            if prompt_path
            else (Path(__file__).resolve().parents[2] / "prompts" / "devgodzilla-protocol-generate.prompt.md")
        )

        if not prompt_path.is_file():
            return ProtocolGenerationResult(
                success=False,
                engine_id=engine_id,
                model=model,
                worktree_root=worktree_root,
                protocol_root=protocol_root,
                prompt_path=prompt_path,
                created_files=[],
                error=f"Prompt not found: {prompt_path}",
            )

        registry = get_registry()
        if not registry.list_ids():
            try:
                from devgodzilla.engines.bootstrap import bootstrap_default_engines

                bootstrap_default_engines(replace=False)
            except Exception:
                pass
        try:
            engine = registry.get(engine_id)
        except EngineNotFoundError as e:
            return ProtocolGenerationResult(
                success=False,
                engine_id=engine_id,
                model=model,
                worktree_root=worktree_root,
                protocol_root=protocol_root,
                prompt_path=prompt_path,
                created_files=[],
                error=f"Engine not registered: {e}",
            )

        if not engine.check_availability():
            return ProtocolGenerationResult(
                success=False,
                engine_id=engine_id,
                model=model,
                worktree_root=worktree_root,
                protocol_root=protocol_root,
                prompt_path=prompt_path,
                created_files=[],
                error=f"Engine unavailable: {engine_id}",
            )

        env_model: Optional[str] = None
        if model is None and engine.metadata.id == "opencode":
            candidate = os.environ.get("DEVGODZILLA_OPENCODE_MODEL")
            if isinstance(candidate, str) and candidate.strip():
                env_model = candidate.strip()

        resolved_agent_model: Optional[str] = None
        if model is None and env_model is None and project_id is not None:
            try:
                cfg = AgentConfigService(self.context)
                agent_cfg = cfg.get_agent(engine_id, project_id=project_id)
                if agent_cfg and isinstance(agent_cfg.default_model, str) and agent_cfg.default_model.strip():
                    resolved_agent_model = agent_cfg.default_model.strip()
            except Exception:
                resolved_agent_model = None

        run_model = model or env_model or resolved_agent_model or engine.metadata.default_model

        template = prompt_path.read_text(encoding="utf-8")
        prompt_text = _render_prompt(
            template,
            protocol_name=protocol_name,
            description=description,
            step_count=max(1, int(step_count)),
            workflow_context=workflow_context,
        )

        req = EngineRequest(
            project_id=None,
            protocol_run_id=None,
            step_run_id=None,
            model=run_model,
            prompt_text=prompt_text,
            prompt_files=[str(prompt_path)],
            working_dir=str(worktree_root),
            sandbox=SandboxMode.WORKSPACE_WRITE,
            timeout=timeout_seconds,
            extra={"job_id": "protocol_generate"},
        )
        engine_result = engine.execute(req)

        created_files = sorted(protocol_root.glob("*.md")) if protocol_root.exists() else []

        missing: list[str] = []
        if strict_outputs:
            if not protocol_root.exists():
                missing.append(str(protocol_root))
            else:
                required = [protocol_root / "plan.md"]
                required.extend(sorted(protocol_root.glob("step-*.md")))
                if not (protocol_root / "plan.md").exists():
                    missing.append("plan.md")
                if len(list(protocol_root.glob("step-*.md"))) == 0:
                    missing.append("step-*.md")
                for p in required:
                    if p.exists() and p.stat().st_size == 0:
                        missing.append(f"empty:{p.name}")

        success = engine_result.success and (not missing if strict_outputs else True)
        error = engine_result.error
        if missing and strict_outputs:
            error = f"Missing protocol outputs: {', '.join(missing)}"

        return ProtocolGenerationResult(
            success=success,
            engine_id=engine_id,
            model=run_model,
            worktree_root=worktree_root,
            protocol_root=protocol_root,
            prompt_path=prompt_path,
            created_files=created_files,
            stdout=engine_result.stdout,
            stderr=engine_result.stderr,
            error=error,
        )
