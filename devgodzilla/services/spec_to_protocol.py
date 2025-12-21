"""
SpecKit to Protocol Adapter

Translates SpecKit tasks into protocol step files under specs/<feature>/_runtime
and creates a ProtocolRun with a stored ProtocolSpec.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from devgodzilla.logging import get_logger
from devgodzilla.spec import PROTOCOL_SPEC_KEY, build_spec_from_protocol_files, create_steps_from_spec
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)


@dataclass
class SpecToProtocolResult:
    success: bool
    protocol_run_id: Optional[int] = None
    protocol_root: Optional[str] = None
    step_count: int = 0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


class SpecToProtocolService(Service):
    def __init__(self, context: ServiceContext, db) -> None:
        super().__init__(context)
        self.db = db

    def create_protocol_from_spec(
        self,
        *,
        project_id: int,
        spec_path: Optional[str] = None,
        tasks_path: Optional[str] = None,
        protocol_name: Optional[str] = None,
        spec_run_id: Optional[int] = None,
        overwrite: bool = False,
    ) -> SpecToProtocolResult:
        project = self.db.get_project(project_id)
        if not project.local_path:
            return SpecToProtocolResult(success=False, error="Project has no local_path")

        repo_root = Path(project.local_path).expanduser()
        spec_run = None
        if spec_run_id:
            try:
                spec_run = self.db.get_spec_run(spec_run_id)
            except Exception:
                spec_run = None
        if spec_run and spec_run.worktree_path:
            repo_root = Path(spec_run.worktree_path).expanduser()
        resolved_spec_path, resolved_tasks_path, spec_dir = self._resolve_paths(
            repo_root,
            spec_path=spec_path,
            tasks_path=tasks_path,
        )
        if not resolved_tasks_path or not resolved_tasks_path.exists():
            return SpecToProtocolResult(
                success=False,
                error=f"Tasks file not found: {resolved_tasks_path or tasks_path}",
            )

        protocol_name = protocol_name or (spec_run.spec_name if spec_run else spec_dir.name)
        protocol_root = spec_dir / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)

        warnings: List[str] = []
        existing_steps = sorted(protocol_root.glob("step-*.md"))
        if existing_steps and not overwrite:
            warnings.append("Existing runtime steps found; leaving files unchanged")
        else:
            phases = self._parse_tasks_by_phase(resolved_tasks_path.read_text(encoding="utf-8"))
            if not phases:
                return SpecToProtocolResult(success=False, error="No tasks found in tasks.md")
            self._write_step_files(
                protocol_root=protocol_root,
                phases=phases,
                spec_path=resolved_spec_path,
                plan_path=spec_dir / "plan.md",
                tasks_path=resolved_tasks_path,
            )
            self._write_runtime_plan(
                protocol_root=protocol_root,
                spec_path=resolved_spec_path,
                plan_path=spec_dir / "plan.md",
                tasks_path=resolved_tasks_path,
                phase_titles=[title for title, _ in phases],
                overwrite=overwrite,
            )
            self._ensure_runtime_support_files(protocol_root, protocol_name)

        run = self.db.create_protocol_run(
            project_id=project_id,
            protocol_name=protocol_name,
            status="planned",
            base_branch=project.base_branch or "main",
            description=f"SpecKit protocol for {protocol_name}",
            worktree_path=str(repo_root),
        )
        try:
            protocol_root_value = str(protocol_root.relative_to(repo_root))
        except Exception:
            protocol_root_value = str(protocol_root)
        self.db.update_protocol_paths(run.id, protocol_root=protocol_root_value)
        if spec_run_id:
            try:
                self.db.update_spec_run(spec_run_id, protocol_run_id=run.id)
            except Exception:
                pass

        default_engine_id = None
        try:
            from devgodzilla.services.agent_config import AgentConfigService

            cfg = AgentConfigService(self.context, db=self.db)
            candidate = cfg.get_default_engine_id(
                "exec",
                project_id=project_id,
                fallback=self.context.config.engine_defaults.get("exec"),  # type: ignore[union-attr]
            )
            if isinstance(candidate, str) and candidate.strip():
                default_engine_id = candidate.strip()
        except Exception:
            default_engine_id = None

        default_qa_prompt = None
        try:
            from devgodzilla.services.agent_config import AgentConfigService
            from devgodzilla.spec import resolve_spec_path

            cfg = AgentConfigService(self.context, db=self.db)
            assignment = cfg.resolve_prompt_assignment("qa", project_id=project_id)
            if assignment and assignment.get("path"):
                candidate = resolve_spec_path(
                    str(assignment["path"]),
                    repo_root,
                    repo_root,
                )
                if candidate.exists():
                    default_qa_prompt = str(assignment["path"])
        except Exception:
            default_qa_prompt = None

        protocol_spec = build_spec_from_protocol_files(
            protocol_root,
            default_engine_id=default_engine_id,
            default_qa_prompt=default_qa_prompt or "prompts/quality-validator.prompt.md",
        )
        template_config = {PROTOCOL_SPEC_KEY: protocol_spec}
        self.db.update_protocol_template(run.id, template_config=template_config)

        step_ids = create_steps_from_spec(self.db, run.id, protocol_spec)
        self.db.update_protocol_status(run.id, "planned")

        speckit_metadata = self._build_speckit_metadata(
            repo_root=repo_root,
            spec_path=resolved_spec_path,
            plan_path=spec_dir / "plan.md",
            tasks_path=resolved_tasks_path,
            protocol_root=protocol_root,
        )
        self.db.update_protocol_windmill(run.id, speckit_metadata=speckit_metadata)

        return SpecToProtocolResult(
            success=True,
            protocol_run_id=run.id,
            protocol_root=str(protocol_root),
            step_count=len(step_ids),
            warnings=warnings,
        )

    def _resolve_paths(
        self,
        repo_root: Path,
        *,
        spec_path: Optional[str],
        tasks_path: Optional[str],
    ) -> Tuple[Optional[Path], Optional[Path], Path]:
        resolved_spec_path = self._resolve_path(repo_root, spec_path)
        resolved_tasks_path = self._resolve_path(repo_root, tasks_path)
        if resolved_spec_path:
            spec_dir = resolved_spec_path.parent
        elif resolved_tasks_path:
            spec_dir = resolved_tasks_path.parent
        else:
            spec_dir = repo_root
        if resolved_tasks_path is None and spec_dir:
            candidate = spec_dir / "tasks.md"
            resolved_tasks_path = candidate if candidate.exists() else None
        if resolved_spec_path is None and spec_dir:
            candidate = spec_dir / "spec.md"
            resolved_spec_path = candidate if candidate.exists() else None
        return resolved_spec_path, resolved_tasks_path, spec_dir

    @staticmethod
    def _resolve_path(repo_root: Path, value: Optional[str]) -> Optional[Path]:
        if not value:
            return None
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        return repo_root / candidate

    @staticmethod
    def _parse_tasks_by_phase(content: str) -> List[Tuple[str, List[str]]]:
        phases: List[Tuple[str, List[str]]] = []
        current_title = "Tasks"
        current_tasks: List[str] = []

        heading_re = re.compile(r"^#{2,6}\s+(.*)$")
        task_re = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.+)$")

        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            heading_match = heading_re.match(line)
            if heading_match:
                if current_tasks:
                    phases.append((current_title, current_tasks))
                current_title = heading_match.group(1).strip()
                current_tasks = []
                continue

            task_match = task_re.match(line)
            if task_match:
                current_tasks.append(task_match.group(0).strip())

        if current_tasks:
            phases.append((current_title, current_tasks))
        return phases

    def _write_step_files(
        self,
        *,
        protocol_root: Path,
        phases: List[Tuple[str, List[str]]],
        spec_path: Optional[Path],
        plan_path: Path,
        tasks_path: Path,
    ) -> None:
        seen_names: Dict[str, int] = {}
        for idx, (title, tasks) in enumerate(phases, start=1):
            slug = self._slugify(title)
            count = seen_names.get(slug, 0)
            seen_names[slug] = count + 1
            if count:
                slug = f"{slug}-{count + 1}"
            step_name = f"step-{idx:02d}-{slug}"
            step_path = protocol_root / f"{step_name}.md"
            content = self._render_step_content(
                step_name=step_name,
                title=title,
                tasks=tasks,
                spec_path=spec_path,
                plan_path=plan_path,
                tasks_path=tasks_path,
            )
            step_path.write_text(content, encoding="utf-8")

    def _write_runtime_plan(
        self,
        *,
        protocol_root: Path,
        spec_path: Optional[Path],
        plan_path: Path,
        tasks_path: Path,
        phase_titles: List[str],
        overwrite: bool,
    ) -> None:
        plan_file = protocol_root / "plan.md"
        if plan_file.exists() and not overwrite:
            return
        plan_content = [
            f"# Protocol Plan: {protocol_root.parent.name}",
            "",
            "## Source Artifacts",
        ]
        if spec_path:
            plan_content.append(f"- Spec: {spec_path}")
        if plan_path.exists():
            plan_content.append(f"- Plan: {plan_path}")
        if tasks_path.exists():
            plan_content.append(f"- Tasks: {tasks_path}")
        plan_content.append("")
        if plan_path.exists():
            try:
                plan_text = plan_path.read_text(encoding="utf-8").strip()
            except Exception:
                plan_text = ""
            if plan_text:
                plan_content.extend(["## Implementation Plan (source)", plan_text, ""])
        plan_content.append("## Steps")
        for idx, title in enumerate(phase_titles, start=1):
            plan_content.append(f"- Step {idx:02d}: {title}")
        plan_file.write_text("\n".join(plan_content).rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def _ensure_runtime_support_files(protocol_root: Path, feature_name: str) -> None:
        context_path = protocol_root / "context.md"
        log_path = protocol_root / "log.md"
        if not context_path.exists():
            context_path.write_text(f"# Execution Context: {feature_name}\n\n", encoding="utf-8")
        if not log_path.exists():
            log_path.write_text(f"# Execution Log: {feature_name}\n\n", encoding="utf-8")
        (protocol_root / "runs").mkdir(exist_ok=True)

    @staticmethod
    def _render_step_content(
        *,
        step_name: str,
        title: str,
        tasks: List[str],
        spec_path: Optional[Path],
        plan_path: Path,
        tasks_path: Path,
    ) -> str:
        lines = [f"# {step_name}: {title}", "", "## Goal", f"Execute tasks for: {title}", ""]
        lines.extend(["## Inputs"])
        if spec_path:
            lines.append(f"- Spec: {spec_path}")
        if plan_path.exists():
            lines.append(f"- Plan: {plan_path}")
        if tasks_path.exists():
            lines.append(f"- Tasks: {tasks_path}")
        lines.append("")
        lines.extend(["## Tasks"])
        lines.extend(tasks or ["- [ ] Review tasks.md and clarify missing items"])
        lines.append("")
        lines.extend([
            "## Notes",
            "- Follow project policy and constitution in `.specify/memory/constitution.md`.",
            "- Update relevant code/tests/docs as needed for this phase.",
        ])
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
        slug = slug.strip("-")
        return slug or "phase"

    @staticmethod
    def _build_speckit_metadata(
        *,
        repo_root: Path,
        spec_path: Optional[Path],
        plan_path: Path,
        tasks_path: Path,
        protocol_root: Path,
    ) -> Dict[str, str]:
        def _rel(path: Optional[Path]) -> Optional[str]:
            if not path:
                return None
            try:
                return str(path.relative_to(repo_root))
            except Exception:
                return str(path)

        return {
            "spec_path": _rel(spec_path),
            "plan_path": _rel(plan_path) if plan_path.exists() else None,
            "tasks_path": _rel(tasks_path),
            "protocol_root": _rel(protocol_root),
        }
