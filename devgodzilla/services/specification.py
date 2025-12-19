"""
DevGodzilla Specification Service

Manages SpecKit integration, .specify directory structure, and spec-driven
development workflow.

Current implementation is agent-assisted:
- creates `.specify/` structure (constitution + templates)
- generates `spec.md`, `plan.md`, `tasks.md` via SWE agents using prompts

No external `specify` binary is required for the current code path.
"""

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.engines import EngineNotFoundError, EngineRequest, SandboxMode, get_registry
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.speckit_adapter import SpecKitAdapter


@dataclass
class SpecKitResult:
    """Result from a SpecKit operation."""
    success: bool
    project_id: Optional[int] = None
    spec_path: Optional[str] = None
    constitution_hash: Optional[str] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class SpecifyResult:
    """Result from spec generation."""
    success: bool
    spec_path: Optional[str] = None
    spec_number: Optional[int] = None
    feature_name: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PlanResult:
    """Result from plan generation."""
    success: bool
    plan_path: Optional[str] = None
    data_model_path: Optional[str] = None
    contracts_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TasksResult:
    """Result from task generation."""
    success: bool
    tasks_path: Optional[str] = None
    task_count: int = 0
    parallelizable_count: int = 0
    error: Optional[str] = None


@dataclass
class ClarifyResult:
    """Result from spec clarification."""
    success: bool
    spec_path: Optional[str] = None
    clarifications_added: int = 0
    error: Optional[str] = None


@dataclass
class ChecklistResult:
    """Result from checklist generation."""
    success: bool
    checklist_path: Optional[str] = None
    item_count: int = 0
    error: Optional[str] = None


@dataclass
class AnalyzeResult:
    """Result from analysis generation."""
    success: bool
    report_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ImplementResult:
    """Result from implementation run scaffolding."""
    success: bool
    run_path: Optional[str] = None
    metadata_path: Optional[str] = None
    error: Optional[str] = None


class SpecificationService(Service):
    """
    Manages the SpecKit integration and .specify directory structure.

    Generates SpecKit-style artifacts by seeding templates and invoking
    SWE agents to fill in the documentation.
    """

    DOT_SPECIFY = ".specify"
    MEMORY_DIR = "memory"
    TEMPLATES_DIR = "templates"
    SPECS_DIR = "specs"
    SPECIFY_PROMPT = "devgodzilla-speckit-specify.prompt.md"
    PLAN_PROMPT = "devgodzilla-speckit-plan.prompt.md"
    TASKS_PROMPT = "devgodzilla-speckit-tasks.prompt.md"
    CHECKLIST_PROMPT = "devgodzilla-speckit-checklist.prompt.md"
    ANALYZE_PROMPT = "devgodzilla-speckit-analyze.prompt.md"

    def __init__(
        self,
        context: ServiceContext,
        db=None,
        *,
        speckit_cli_path: Optional[str] = None,
        speckit_source_path: Optional[str] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.speckit_cli = speckit_cli_path or "specify"
        self.speckit_source_path = Path(speckit_source_path).expanduser() if speckit_source_path else None

    def init_project(
        self,
        project_path: str,
        constitution_content: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> SpecKitResult:
        """
        Initialize the .specify directory structure in a project.

        Structure:
        .specify/
        ├── memory/
        │   └── constitution.md
        ├── templates/
        │   ├── spec-template.md
        │   ├── plan-template.md
        │   └── tasks-template.md
        specs/

        Args:
            project_path: Path to the project root
            constitution_content: Optional custom constitution content
            project_id: Optional project ID for DB tracking

        Returns:
            SpecKitResult with success status and paths
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)
        base_path = Path(project_path)
        specify_path = base_path / self.DOT_SPECIFY

        if specify_path.exists():
            specs_dir = base_path / "specs"
            if not specs_dir.exists():
                specs_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("specify_dir_exists", extra=log_extra)
            constitution_hash = self._compute_constitution_hash(specify_path)
            return SpecKitResult(
                success=True,
                project_id=project_id,
                spec_path=str(specify_path),
                constitution_hash=constitution_hash,
                warnings=["Directory already exists"],
            )

        try:
            (specify_path / self.MEMORY_DIR).mkdir(parents=True, exist_ok=True)
            (specify_path / self.TEMPLATES_DIR).mkdir(parents=True, exist_ok=True)
            specs_dir = base_path / "specs"
            specs_dir.mkdir(parents=True, exist_ok=True)

            speckit_source = self._resolve_speckit_source()

            constitution_path = specify_path / self.MEMORY_DIR / "constitution.md"
            if constitution_content:
                constitution_path.write_text(constitution_content)
            elif speckit_source and (speckit_source / "memory" / "constitution.md").exists():
                self._copy_file_if_missing(
                    speckit_source / "memory" / "constitution.md",
                    constitution_path,
                )
            else:
                self._create_default_constitution(constitution_path)

            if speckit_source and (speckit_source / "templates").exists():
                self._copy_dir_contents(
                    speckit_source / "templates",
                    specify_path / self.TEMPLATES_DIR,
                )
            else:
                self._create_default_templates(specify_path / self.TEMPLATES_DIR)

            if speckit_source and (speckit_source / "scripts").exists():
                self._copy_dir_contents(
                    speckit_source / "scripts",
                    specify_path / "scripts",
                )

            constitution_hash = self._compute_constitution_hash(specify_path)

            if self.db and project_id:
                self._update_project_constitution(project_id, constitution_hash)

            self.logger.info("speckit_initialized", extra={**log_extra, "constitution_hash": constitution_hash})

            return SpecKitResult(
                success=True,
                project_id=project_id,
                spec_path=str(specify_path),
                constitution_hash=constitution_hash,
                artifacts={
                    "constitution": str(constitution_path),
                    "templates": str(specify_path / self.TEMPLATES_DIR),
                    "specs": str(specs_dir),
                },
            )

        except Exception as e:
            self.logger.error("speckit_init_failed", extra={**log_extra, "error": str(e)})
            return SpecKitResult(
                success=False,
                project_id=project_id,
                error=f"Initialization failed: {e}",
            )

    def get_constitution(self, project_path: str) -> Optional[str]:
        """
        Get the project constitution content.

        Args:
            project_path: Path to the project root

        Returns:
            Constitution content or None if not found
        """
        path = Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / "constitution.md"
        if path.exists():
            return path.read_text()
        return None

    def save_constitution(
        self,
        project_path: str,
        content: str,
        project_id: Optional[int] = None,
    ) -> SpecKitResult:
        """
        Save constitution content to the project.

        Args:
            project_path: Path to the project root
            content: Constitution content to save
            project_id: Optional project ID for DB tracking

        Returns:
            SpecKitResult with success status
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            path = Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / "constitution.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

            constitution_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

            if self.db and project_id:
                self._update_project_constitution(project_id, constitution_hash)

            self.logger.info("constitution_saved", extra={**log_extra, "constitution_hash": constitution_hash})

            return SpecKitResult(
                success=True,
                project_id=project_id,
                spec_path=str(path),
                constitution_hash=constitution_hash,
            )
        except Exception as e:
            self.logger.error("constitution_save_failed", extra={**log_extra, "error": str(e)})
            return SpecKitResult(
                success=False,
                project_id=project_id,
                error=f"Failed to save constitution: {e}",
            )

    def run_specify(
        self,
        project_path: str,
        description: str,
        feature_name: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> SpecifyResult:
        """
        Generate a feature specification by filling the spec template.

        Args:
            project_path: Path to the project root
            description: Feature description in natural language
            feature_name: Optional feature name (auto-generated if not provided)
            project_id: Optional project ID for logging

        Returns:
            SpecifyResult with spec path and metadata
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            policy_guidelines = self._policy_guidelines_text(project_path, project_id)
            adapter = self._get_speckit_adapter(project_path)
            if adapter and adapter.supports("specify"):
                script_result = adapter.create_feature(
                    description,
                    short_name=feature_name,
                )
                if script_result.success:
                    spec_path_str = script_result.data.get("SPEC_FILE")
                    branch_name = script_result.data.get("BRANCH_NAME")
                    spec_number = int(script_result.data.get("FEATURE_NUM", "0") or 0)
                    resolved_feature_name = feature_name or self._infer_feature_name(branch_name)
                    if spec_path_str:
                        spec_path = Path(spec_path_str)
                        self._ensure_runtime_dir(spec_path.parent, resolved_feature_name)
                    else:
                        spec_path = self._resolve_specs_dir(project_path) / f"{spec_number:03d}-{resolved_feature_name}" / "spec.md"

                    self._ensure_runtime_dir(spec_path.parent, resolved_feature_name)

                    if spec_path.exists():
                        self._apply_template_values(
                            spec_path,
                            {
                                "title": resolved_feature_name,
                                "description": description,
                                "spec_number": spec_number,
                                "branch_name": branch_name or spec_path.parent.name,
                                "date": datetime.utcnow().date().isoformat(),
                                "policy_guidelines": policy_guidelines,
                            },
                        )
                        self._append_policy_guidelines(spec_path, policy_guidelines)
                    else:
                        spec_path.parent.mkdir(parents=True, exist_ok=True)
                        template = self._load_template(project_path, "spec-template.md")
                        spec_content = self._fill_template(template, {
                            "title": resolved_feature_name,
                            "description": description,
                            "spec_number": spec_number,
                            "branch_name": branch_name or spec_path.parent.name,
                            "date": datetime.utcnow().date().isoformat(),
                            "policy_guidelines": policy_guidelines,
                        })
                        spec_path.write_text(spec_content)
                        self._append_policy_guidelines(spec_path, policy_guidelines)

                    spec_dir = spec_path.parent
                    prompt_context = self._format_prompt_context(
                        "SpecKit specification context",
                        [
                            f"Repo root: {Path(project_path).expanduser()}",
                            f"Feature name: {resolved_feature_name}",
                            f"Feature description: {description}",
                            f"Spec directory: {spec_dir}",
                            f"Spec file: {spec_path}",
                            f"Spec template: {Path(project_path) / self.DOT_SPECIFY / self.TEMPLATES_DIR / 'spec-template.md'}",
                            f"Constitution: {Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / 'constitution.md'}",
                        ],
                        policy_guidelines,
                    )
                    agent_result = self._run_speckit_agent(
                        project_path,
                        prompt_name=self.SPECIFY_PROMPT,
                        prompt_context=prompt_context,
                        job_id="speckit_specify",
                        project_id=project_id,
                    )
                    if not agent_result.success:
                        return SpecifyResult(
                            success=False,
                            error=agent_result.error or "Spec generation failed",
                        )
                    self._append_policy_guidelines(spec_path, policy_guidelines)

                    self.logger.info("spec_generated", extra={
                        **log_extra,
                        "spec_number": spec_number,
                        "feature_name": resolved_feature_name,
                    })
                    self._append_policy_clarifications(project_path, str(spec_path), project_id)
                    self._persist_policy_clarifications(project_path, project_id, applies_to="specify")
                    return SpecifyResult(
                        success=True,
                        spec_path=str(spec_path),
                        spec_number=spec_number or None,
                        feature_name=resolved_feature_name,
                    )

            spec_number = self._get_next_spec_number(project_path)
            if not feature_name:
                feature_name = self._sanitize_feature_name(description[:50])

            spec_dir = self._resolve_specs_dir(project_path) / f"{spec_number:03d}-{feature_name}"
            spec_dir.mkdir(parents=True, exist_ok=True)

            spec_path = spec_dir / "spec.md"

            self._ensure_runtime_dir(spec_dir, feature_name)

            template = self._load_template(project_path, "spec-template.md")
            branch_name = spec_dir.name
            spec_content = self._fill_template(template, {
                "title": feature_name,
                "description": description,
                "spec_number": spec_number,
                "branch_name": branch_name,
                "date": datetime.utcnow().date().isoformat(),
                "policy_guidelines": policy_guidelines,
            })
            spec_path.write_text(spec_content)
            self._append_policy_guidelines(spec_path, policy_guidelines)

            prompt_context = self._format_prompt_context(
                "SpecKit specification context",
                [
                    f"Repo root: {Path(project_path).expanduser()}",
                    f"Feature name: {feature_name}",
                    f"Feature description: {description}",
                    f"Spec directory: {spec_dir}",
                    f"Spec file: {spec_path}",
                    f"Spec template: {Path(project_path) / self.DOT_SPECIFY / self.TEMPLATES_DIR / 'spec-template.md'}",
                    f"Constitution: {Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / 'constitution.md'}",
                ],
                policy_guidelines,
            )
            agent_result = self._run_speckit_agent(
                project_path,
                prompt_name=self.SPECIFY_PROMPT,
                prompt_context=prompt_context,
                job_id="speckit_specify",
                project_id=project_id,
            )
            if not agent_result.success:
                return SpecifyResult(
                    success=False,
                    error=agent_result.error or "Spec generation failed",
                )
            self._append_policy_guidelines(spec_path, policy_guidelines)

            self.logger.info("spec_generated", extra={
                **log_extra,
                "spec_number": spec_number,
                "feature_name": feature_name,
            })

            self._append_policy_clarifications(project_path, str(spec_path), project_id)
            self._persist_policy_clarifications(project_path, project_id, applies_to="specify")

            return SpecifyResult(
                success=True,
                spec_path=str(spec_path),
                spec_number=spec_number,
                feature_name=feature_name,
            )

        except Exception as e:
            self.logger.error("spec_generation_failed", extra={**log_extra, "error": str(e)})
            return SpecifyResult(
                success=False,
                error=f"Spec generation failed: {e}",
            )

    def run_plan(
        self,
        project_path: str,
        spec_path: str,
        project_id: Optional[int] = None,
    ) -> PlanResult:
        """
        Generate an implementation plan from a spec.

        Args:
            project_path: Path to the project root
            spec_path: Path to the spec.md file
            project_id: Optional project ID for logging

        Returns:
            PlanResult with plan paths
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            policy_guidelines = self._policy_guidelines_text(project_path, project_id)
            spec_dir = Path(spec_path).parent
            plan_path: Path
            adapter = self._get_speckit_adapter(project_path)

            if adapter and adapter.supports("plan"):
                script_result = adapter.setup_plan(feature_name=spec_dir.name)
                if script_result.success:
                    plan_path = Path(script_result.data.get("IMPL_PLAN", spec_dir / "plan.md"))
                else:
                    plan_path = spec_dir / "plan.md"
            else:
                plan_path = spec_dir / "plan.md"

            if not plan_path.exists():
                template = self._load_template(project_path, "plan-template.md")
                plan_path.write_text(template)

            spec_content = Path(spec_path).read_text()
            title = self._extract_title(spec_content)

            branch_name = spec_dir.name
            self._apply_template_values(
                plan_path,
                {
                    "title": title,
                    "description": f"Implementation plan for {title}",
                    "branch_name": branch_name,
                    "date": datetime.utcnow().date().isoformat(),
                    "spec_path": spec_path,
                    "policy_guidelines": policy_guidelines,
                },
            )
            self._append_policy_guidelines(plan_path, policy_guidelines)

            data_model_path = spec_dir / "data-model.md"
            if not data_model_path.exists():
                data_model_path.write_text(f"# Data Model: {title}\n\n## Entities\n\n(To be defined)\n")

            research_path = spec_dir / "research.md"
            if not research_path.exists():
                research_path.write_text(f"# Research: {title}\n\n## Notes\n\n(To be defined)\n")

            quickstart_path = spec_dir / "quickstart.md"
            if not quickstart_path.exists():
                quickstart_path.write_text(f"# Quickstart: {title}\n\n## Steps\n\n(To be defined)\n")

            contracts_dir = spec_dir / "contracts"
            contracts_dir.mkdir(exist_ok=True)

            prompt_context = self._format_prompt_context(
                "SpecKit planning context",
                [
                    f"Repo root: {Path(project_path).expanduser()}",
                    f"Spec file: {spec_path}",
                    f"Plan file: {plan_path}",
                    f"Data model file: {data_model_path}",
                    f"Research file: {research_path}",
                    f"Quickstart file: {quickstart_path}",
                    f"Contracts directory: {contracts_dir}",
                    f"Plan template: {Path(project_path) / self.DOT_SPECIFY / self.TEMPLATES_DIR / 'plan-template.md'}",
                    f"Constitution: {Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / 'constitution.md'}",
                ],
                policy_guidelines,
            )
            agent_result = self._run_speckit_agent(
                project_path,
                prompt_name=self.PLAN_PROMPT,
                prompt_context=prompt_context,
                job_id="speckit_plan",
                project_id=project_id,
            )
            if not agent_result.success:
                return PlanResult(
                    success=False,
                    error=agent_result.error or "Plan generation failed",
                )
            self._append_policy_guidelines(plan_path, policy_guidelines)
            self._persist_policy_clarifications(project_path, project_id, applies_to="planning")

            self.logger.info("plan_generated", extra={**log_extra, "plan_path": str(plan_path)})

            return PlanResult(
                success=True,
                plan_path=str(plan_path),
                data_model_path=str(data_model_path),
                contracts_path=str(contracts_dir),
            )

        except Exception as e:
            self.logger.error("plan_generation_failed", extra={**log_extra, "error": str(e)})
            return PlanResult(
                success=False,
                error=f"Plan generation failed: {e}",
            )

    def run_tasks(
        self,
        project_path: str,
        plan_path: str,
        project_id: Optional[int] = None,
    ) -> TasksResult:
        """
        Generate a task list from a plan.

        Args:
            project_path: Path to the project root
            plan_path: Path to the plan.md file
            project_id: Optional project ID for logging

        Returns:
            TasksResult with tasks metadata
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            policy_guidelines = self._policy_guidelines_text(project_path, project_id)
            plan_dir = Path(plan_path).parent

            tasks_path = plan_dir / "tasks.md"
            template = self._load_template(project_path, "tasks-template.md")

            plan_content = Path(plan_path).read_text()
            title = self._extract_title(plan_content)

            branch_name = plan_dir.name
            tasks_content = self._fill_template(template, {
                "title": title,
                "branch_name": branch_name,
                "date": datetime.utcnow().date().isoformat(),
            })
            tasks_path.write_text(tasks_content)

            prompt_context = self._format_prompt_context(
                "SpecKit task generation context",
                [
                    f"Repo root: {Path(project_path).expanduser()}",
                    f"Plan file: {plan_path}",
                    f"Tasks file: {tasks_path}",
                    f"Tasks template: {Path(project_path) / self.DOT_SPECIFY / self.TEMPLATES_DIR / 'tasks-template.md'}",
                    f"Constitution: {Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / 'constitution.md'}",
                ],
                policy_guidelines,
            )
            agent_result = self._run_speckit_agent(
                project_path,
                prompt_name=self.TASKS_PROMPT,
                prompt_context=prompt_context,
                job_id="speckit_tasks",
                project_id=project_id,
            )
            if not agent_result.success:
                return TasksResult(
                    success=False,
                    error=agent_result.error or "Task generation failed",
                )

            tasks_content = tasks_path.read_text()
            task_count = tasks_content.count("- [ ]")
            parallelizable_count = tasks_content.count("[P]")

            self.logger.info("tasks_generated", extra={
                **log_extra,
                "tasks_path": str(tasks_path),
                "task_count": task_count,
            })

            return TasksResult(
                success=True,
                tasks_path=str(tasks_path),
                task_count=task_count,
                parallelizable_count=parallelizable_count,
            )

        except Exception as e:
            self.logger.error("tasks_generation_failed", extra={**log_extra, "error": str(e)})
            return TasksResult(
                success=False,
                error=f"Tasks generation failed: {e}",
            )

    def run_clarify(
        self,
        project_path: str,
        spec_path: str,
        entries: Optional[List[Dict[str, str]]] = None,
        notes: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> ClarifyResult:
        """
        Append clarifications to a specification file.
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            spec_file = Path(spec_path)
            if not spec_file.exists():
                return ClarifyResult(success=False, error="Spec file not found.")

            clarifications = entries or []
            if notes:
                clarifications.append({"question": "Notes", "answer": notes})

            content = spec_file.read_text()
            updated, added = self._append_clarifications(content, clarifications)
            spec_file.write_text(updated)

            self.logger.info("spec_clarified", extra={**log_extra, "clarifications": added})
            return ClarifyResult(
                success=True,
                spec_path=str(spec_file),
                clarifications_added=added,
            )
        except Exception as e:
            self.logger.error("spec_clarify_failed", extra={**log_extra, "error": str(e)})
            return ClarifyResult(
                success=False,
                error=f"Clarify failed: {e}",
            )

    def run_checklist(
        self,
        project_path: str,
        spec_path: str,
        project_id: Optional[int] = None,
    ) -> ChecklistResult:
        """
        Generate a checklist file for a spec.
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            policy_guidelines = self._policy_guidelines_text(project_path, project_id)
            spec_dir = Path(spec_path).parent
            checklist_path = spec_dir / "checklist.md"
            template = self._load_template(project_path, "checklist-template.md")
            checklist_path.write_text(template)

            title = self._extract_title(Path(spec_path).read_text())
            self._apply_template_values(
                checklist_path,
                {
                    "title": title,
                    "branch_name": spec_dir.name,
                    "date": datetime.utcnow().date().isoformat(),
                },
            )

            prompt_context = self._format_prompt_context(
                "SpecKit checklist context",
                [
                    f"Repo root: {Path(project_path).expanduser()}",
                    f"Spec file: {spec_path}",
                    f"Checklist file: {checklist_path}",
                    f"Checklist template: {Path(project_path) / self.DOT_SPECIFY / self.TEMPLATES_DIR / 'checklist-template.md'}",
                    f"Constitution: {Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / 'constitution.md'}",
                ],
                policy_guidelines,
            )
            agent_result = self._run_speckit_agent(
                project_path,
                prompt_name=self.CHECKLIST_PROMPT,
                prompt_context=prompt_context,
                job_id="speckit_checklist",
                project_id=project_id,
            )
            if not agent_result.success:
                return ChecklistResult(
                    success=False,
                    error=agent_result.error or "Checklist generation failed",
                )

            item_count = checklist_path.read_text().count("- [ ]")
            self.logger.info("checklist_generated", extra={**log_extra, "checklist_path": str(checklist_path)})
            return ChecklistResult(
                success=True,
                checklist_path=str(checklist_path),
                item_count=item_count,
            )
        except Exception as e:
            self.logger.error("checklist_generation_failed", extra={**log_extra, "error": str(e)})
            return ChecklistResult(
                success=False,
                error=f"Checklist generation failed: {e}",
            )

    def run_analyze(
        self,
        project_path: str,
        spec_path: str,
        plan_path: Optional[str] = None,
        tasks_path: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> AnalyzeResult:
        """
        Generate a placeholder analysis report.
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            policy_guidelines = self._policy_guidelines_text(project_path, project_id)
            spec_dir = Path(spec_path).parent
            report_path = spec_dir / "analysis.md"
            report_content = [
                "# SpecKit Analysis Report",
                "",
                f"- Spec: {spec_path}",
                f"- Plan: {plan_path or 'N/A'}",
                f"- Tasks: {tasks_path or 'N/A'}",
                "",
                "## Findings",
                "- (To be generated)",
            ]
            report_path.write_text("\n".join(report_content) + "\n")

            prompt_context = self._format_prompt_context(
                "SpecKit analysis context",
                [
                    f"Repo root: {Path(project_path).expanduser()}",
                    f"Spec file: {spec_path}",
                    f"Plan file: {plan_path or 'N/A'}",
                    f"Tasks file: {tasks_path or 'N/A'}",
                    f"Analysis file: {report_path}",
                    f"Constitution: {Path(project_path) / self.DOT_SPECIFY / self.MEMORY_DIR / 'constitution.md'}",
                ],
                policy_guidelines,
            )
            agent_result = self._run_speckit_agent(
                project_path,
                prompt_name=self.ANALYZE_PROMPT,
                prompt_context=prompt_context,
                job_id="speckit_analyze",
                project_id=project_id,
            )
            if not agent_result.success:
                return AnalyzeResult(
                    success=False,
                    error=agent_result.error or "Analyze failed",
                )

            self.logger.info("analysis_generated", extra={**log_extra, "report_path": str(report_path)})
            return AnalyzeResult(
                success=True,
                report_path=str(report_path),
            )
        except Exception as e:
            self.logger.error("analysis_failed", extra={**log_extra, "error": str(e)})
            return AnalyzeResult(
                success=False,
                error=f"Analyze failed: {e}",
            )

    def run_implement(
        self,
        project_path: str,
        spec_path: str,
        project_id: Optional[int] = None,
    ) -> ImplementResult:
        """
        Scaffold a SpecKit implementation run directory.
        """
        log_extra = self.log_extra(project_id=project_id, path=project_path)

        try:
            spec_dir = Path(spec_path).parent
            runtime_dir = spec_dir / "_runtime" / "runs"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
            run_path = runtime_dir / run_id
            run_path.mkdir(parents=True, exist_ok=True)

            metadata_path = run_path / "metadata.json"
            metadata = {
                "run_id": run_id,
                "status": "initialized",
                "spec_path": str(spec_path),
                "created_at": datetime.utcnow().isoformat(),
            }
            metadata_path.write_text(json.dumps(metadata, indent=2))

            self.logger.info("implement_run_initialized", extra={**log_extra, "run_path": str(run_path)})
            return ImplementResult(
                success=True,
                run_path=str(run_path),
                metadata_path=str(metadata_path),
            )
        except Exception as e:
            self.logger.error("implement_failed", extra={**log_extra, "error": str(e)})
            return ImplementResult(
                success=False,
                error=f"Implement failed: {e}",
            )

    def list_specs(self, project_path: str) -> List[Dict[str, Any]]:
        """
        List all specs in a project.

        Args:
            project_path: Path to the project root

        Returns:
            List of spec metadata dictionaries
        """
        specs = []
        seen = set()
        for specs_dir in self._list_specs_dirs(project_path):
            if not specs_dir.exists():
                continue
            for spec_folder in sorted(specs_dir.iterdir()):
                if not spec_folder.is_dir():
                    continue
                if spec_folder.name in seen:
                    continue
                seen.add(spec_folder.name)

                spec_file = spec_folder / "spec.md"
                plan_file = spec_folder / "plan.md"
                tasks_file = spec_folder / "tasks.md"

                specs.append({
                    "name": spec_folder.name,
                    "path": str(spec_folder),
                    "spec_path": str(spec_file) if spec_file.exists() else None,
                    "plan_path": str(plan_file) if plan_file.exists() else None,
                    "tasks_path": str(tasks_file) if tasks_file.exists() else None,
                    "has_spec": spec_file.exists(),
                    "has_plan": plan_file.exists(),
                    "has_tasks": tasks_file.exists(),
                })

        return specs

    def _create_default_constitution(self, path: Path) -> None:
        """Create default constitution file."""
        content = """# Project Constitution

## Core Values

1. **Safety First**: Verify all generated code in sandboxes.
2. **User Control**: Never execute side-effects without approval unless safe.
3. **Library First**: Prefer established libraries over custom implementation.
4. **Test Driven**: Write tests before implementation where possible.
5. **Simplicity**: Avoid over-engineering; prefer simple solutions.

## Quality Gates

- All code must pass linting
- All code must pass type checking
- Tests must pass before merge
- Security scans must pass

## Constraints

- Follow existing code conventions
- Use dependency injection for testability
- Document public APIs
"""
        path.write_text(content)

    def _create_default_templates(self, templates_dir: Path) -> None:
        """Create default template files."""
        (templates_dir / "spec-template.md").write_text("""# Feature Specification: {{ title }}

## Overview
{{ description }}

## User Stories

### P1 - Must Have
- [ ] US1: As a user, I want to...

### P2 - Should Have
- [ ] US2: As a user, I want to...

## Functional Requirements

- FR-001: The system shall...

## Success Criteria

- [ ] Acceptance criteria 1
- [ ] Acceptance criteria 2

## Context

- Existing files: ...
- Dependencies: ...

## Policy Guidelines

{{ policy_guidelines }}
""")

        (templates_dir / "plan-template.md").write_text("""# Implementation Plan: {{ title }}

## Goal
{{ description }}

## Technical Context

- Language/Version: Python 3.11+
- Framework: FastAPI
- Testing: pytest
- Storage: PostgreSQL/SQLite

## Proposed Changes

### Phase 1: Setup
- [ ] Task 1

### Phase 2: Implementation
- [ ] Task 2

## Verification Plan

- [ ] Unit tests for core logic
- [ ] Integration tests for API

## Policy Guidelines

{{ policy_guidelines }}
""")

        (templates_dir / "tasks-template.md").write_text("""# Task List: {{ title }}

## Phase 1: Setup
- [ ] [T001] [P] Setup project structure

## Phase 2: Core Implementation
- [ ] [T002] Implement main feature

## Phase 3: Testing
- [ ] [T003] [P] Write unit tests
- [ ] [T004] [P] Write integration tests

## Phase 4: Documentation
- [ ] [T005] Update README

---
Legend:
- [P] = Parallelizable (can run concurrently with other [P] tasks)
- [US1] = Relates to User Story 1
""")

        (templates_dir / "checklist-template.md").write_text("""# Quality Checklist: {{ title }}

## Code Quality
- [ ] Code follows project style guide
- [ ] No hardcoded values
- [ ] Error handling implemented

## Testing
- [ ] Unit tests written
- [ ] Integration tests written
- [ ] Edge cases covered

## Security
- [ ] No secrets in code
- [ ] Input validation implemented
- [ ] SQL injection prevention

## Documentation
- [ ] Code is self-documenting
- [ ] Public APIs documented
""")

    def _compute_constitution_hash(self, specify_path: Path) -> str:
        """Compute hash of constitution file."""
        constitution_path = specify_path / self.MEMORY_DIR / "constitution.md"
        if constitution_path.exists():
            content = constitution_path.read_text()
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        return ""

    def _update_project_constitution(self, project_id: int, constitution_hash: str) -> None:
        """Update project constitution tracking in DB."""
        if self.db:
            try:
                self.db.update_project(
                    project_id,
                    constitution_version="1.0",
                    constitution_hash=constitution_hash,
                )
            except Exception as e:
                self.logger.warning("constitution_db_update_failed", extra={"error": str(e)})

    def _get_next_spec_number(self, project_path: str) -> int:
        """Get the next spec number."""
        numbers = []
        for specs_dir in self._list_specs_dirs(project_path):
            if not specs_dir.exists():
                continue
            existing = [d.name for d in specs_dir.iterdir() if d.is_dir()]
            for name in existing:
                try:
                    num = int(name.split("-")[0])
                    numbers.append(num)
                except (ValueError, IndexError):
                    pass

        return max(numbers, default=0) + 1

    def _sanitize_feature_name(self, name: str) -> str:
        """Sanitize feature name for filesystem."""
        import re
        name = name.lower().strip()
        name = re.sub(r'[^a-z0-9\s-]', '', name)
        name = re.sub(r'[\s_]+', '-', name)
        name = re.sub(r'-+', '-', name)
        return name.strip('-')[:50]

    def _load_template(self, project_path: str, template_name: str) -> str:
        """Load a template file."""
        template_path = Path(project_path) / self.DOT_SPECIFY / self.TEMPLATES_DIR / template_name
        if template_path.exists():
            return template_path.read_text()
        return f"# {{{{ title }}}}\n\n{{{{ description }}}}\n"

    def _fill_template(self, template: str, values: Dict[str, Any]) -> str:
        """Fill template with values (simple replacement)."""
        result = template
        for key, value in values.items():
            result = result.replace(f"{{{{ {key} }}}}", str(value))
        # SpecKit template compatibility placeholders
        feature_name = values.get("title") or values.get("feature_name")
        branch_name = values.get("branch_name")
        date_value = values.get("date")
        spec_path = values.get("spec_path")
        description = values.get("description")
        replacements = {
            "[FEATURE NAME]": feature_name,
            "[FEATURE]": feature_name,
            "[###-feature-name]": branch_name,
            "[DATE]": date_value,
            "[link]": spec_path,
            "$ARGUMENTS": description,
        }
        for token, value in replacements.items():
            if value is None:
                continue
            result = result.replace(token, str(value))
        return result

    def _extract_title(self, content: str) -> str:
        """Extract title from markdown content."""
        for line in content.split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                if ':' in title:
                    return title.split(':', 1)[1].strip()
                return title
        return "Untitled"

    def _get_speckit_adapter(self, project_path: str) -> Optional[SpecKitAdapter]:
        """Return SpecKit adapter if scripts are available."""
        adapter = SpecKitAdapter(Path(project_path))
        return adapter if adapter.has_scripts() else None

    def _prompt_path(self, prompt_name: str) -> Path:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "prompts" / prompt_name

    def _default_speckit_engine_id(self) -> str:
        env_override = os.environ.get("DEVGODZILLA_SPECKIT_ENGINE_ID")
        if env_override and env_override.strip():
            return env_override.strip()
        try:
            engine_id = self.context.config.engine_defaults.get("planning")  # type: ignore[union-attr]
        except Exception:
            engine_id = None
        if not isinstance(engine_id, str) or not engine_id.strip():
            engine_id = "opencode"
        return engine_id.strip()

    def _default_speckit_model(self) -> Optional[str]:
        env_override = os.environ.get("DEVGODZILLA_SPECKIT_MODEL")
        if env_override and env_override.strip():
            return env_override.strip()
        try:
            model = self.context.config.planning_model  # type: ignore[union-attr]
        except Exception:
            return None
        if isinstance(model, str) and model.strip():
            return model.strip()
        return None

    def _resolve_speckit_engine(
        self,
        engine_id: Optional[str],
        model: Optional[str],
        *,
        project_id: Optional[int] = None,
    ):
        registry = get_registry()
        if not registry.list_ids():
            try:
                from devgodzilla.engines.bootstrap import bootstrap_default_engines

                bootstrap_default_engines(replace=False)
            except Exception:
                pass
        resolved_engine_id = engine_id.strip() if engine_id and engine_id.strip() else self._default_speckit_engine_id()
        try:
            engine = registry.get(resolved_engine_id)
        except EngineNotFoundError:
            engine = registry.get_default()
            resolved_engine_id = engine.metadata.id

        if not engine.check_availability():
            fallback = registry.get_default()
            if fallback.metadata.id != engine.metadata.id:
                self.logger.warning(
                    "speckit_engine_unavailable_fallback",
                    extra=self.log_extra(
                        project_id=project_id,
                        requested_engine_id=engine.metadata.id,
                        fallback_engine_id=fallback.metadata.id,
                    ),
                )
                engine = fallback
                resolved_engine_id = engine.metadata.id

        resolved_model = None
        if isinstance(model, str) and model.strip():
            resolved_model = model.strip()
        if not resolved_model:
            resolved_model = self._default_speckit_model() or engine.metadata.default_model
        return engine, resolved_engine_id, resolved_model

    def _format_prompt_context(
        self,
        header: str,
        lines: List[str],
        policy_guidelines: str,
    ) -> str:
        chunks = [header, ""]
        chunks.extend(f"- {line}" for line in lines)
        if policy_guidelines:
            chunks.extend(["", "Policy guidelines:", policy_guidelines])
        return "\n".join(chunks).strip() + "\n"

    def _run_speckit_agent(
        self,
        project_path: str,
        *,
        prompt_name: str,
        prompt_context: str,
        job_id: str,
        project_id: Optional[int] = None,
        engine_id: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 900,
    ):
        prompt_path = self._prompt_path(prompt_name)
        if not prompt_path.is_file():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")

        engine, resolved_engine_id, resolved_model = self._resolve_speckit_engine(
            engine_id,
            model,
            project_id=project_id,
        )
        request = EngineRequest(
            project_id=project_id or 0,
            protocol_run_id=0,
            step_run_id=0,
            model=resolved_model,
            prompt_text=prompt_context,
            prompt_files=[str(prompt_path)],
            working_dir=str(Path(project_path).expanduser()),
            sandbox=SandboxMode.FULL_ACCESS,
            timeout=timeout_seconds,
            extra={"job_id": job_id, "engine_id": resolved_engine_id},
        )
        return engine.plan(request)

    def _apply_template_values(self, file_path: Path, values: Dict[str, Any]) -> None:
        """Replace template placeholders in an existing file."""
        content = file_path.read_text()
        updated = self._fill_template(content, values)
        if updated != content:
            file_path.write_text(updated)

    def _policy_guidelines_text(self, project_path: str, project_id: Optional[int]) -> str:
        if not self.db or not project_id:
            return ""
        try:
            policy_service = PolicyService(self.context, self.db)
            effective = policy_service.resolve_effective_policy(
                project_id,
                repo_root=Path(project_path),
                include_repo_local=True,
            )
            guidelines = policy_service.build_policy_guidelines(effective)
        except Exception:
            return ""
        header = "## Policy Guidelines"
        if guidelines.strip().startswith(header):
            lines = guidelines.splitlines()[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]
            return "\n".join(lines).strip()
        return guidelines.strip()

    def _append_policy_guidelines(self, file_path: Path, guidelines: str) -> None:
        if not guidelines:
            return
        if not file_path.exists():
            return
        content = file_path.read_text()
        if "## Policy Guidelines" in content:
            return
        updated = content.rstrip() + "\n\n## Policy Guidelines\n\n" + guidelines.strip() + "\n"
        file_path.write_text(updated)

    def _policy_clarification_entries(
        self,
        project_path: str,
        project_id: Optional[int],
        applies_to: set[str],
    ) -> List[Dict[str, str]]:
        if not self.db or not project_id:
            return []
        try:
            policy_service = PolicyService(self.context, self.db)
            effective = policy_service.resolve_effective_policy(
                project_id,
                repo_root=Path(project_path),
                include_repo_local=True,
            )
            clarifications = effective.policy.get("clarifications")
        except Exception:
            return []

        if isinstance(clarifications, dict):
            items = clarifications.get("items") or clarifications.get("questions")
            if isinstance(items, list):
                clarifications = items
            else:
                values = list(clarifications.values())
                if values and all(isinstance(v, dict) for v in values):
                    clarifications = values
                else:
                    clarifications = None

        if not isinstance(clarifications, list):
            return []

        entries: List[Dict[str, str]] = []
        seen = set()
        for item in clarifications:
            if not isinstance(item, dict):
                continue
            question = item.get("question") or item.get("prompt")
            if not isinstance(question, str) or not question.strip():
                continue
            applies = item.get("applies_to") or item.get("appliesTo")
            if applies and str(applies) not in applies_to:
                continue
            recommended = item.get("recommended")
            if isinstance(recommended, dict):
                recommended = recommended.get("value") or recommended.get("answer") or recommended.get("text")
            answer = "" if recommended is None else str(recommended)
            question_text = question.strip()
            if question_text in seen:
                continue
            seen.add(question_text)
            entries.append({"question": question_text, "answer": answer.strip()})
        return entries

    def _append_policy_clarifications(
        self,
        project_path: str,
        spec_path: str,
        project_id: Optional[int],
    ) -> None:
        if not Path(spec_path).exists():
            return
        entries = self._policy_clarification_entries(
            project_path,
            project_id,
            applies_to={"planning", "spec", "specify"},
        )
        if not entries:
            return
        try:
            result = self.run_clarify(
                project_path,
                spec_path,
                entries=entries,
                project_id=project_id,
            )
            if not result.success:
                self.logger.warning(
                    "policy_clarifications_append_failed",
                    extra=self.log_extra(project_id=project_id, path=project_path, error=result.error),
                )
        except Exception as exc:
            self.logger.warning(
                "policy_clarifications_append_failed",
                extra=self.log_extra(project_id=project_id, path=project_path, error=str(exc)),
            )

    def _persist_policy_clarifications(
        self,
        project_path: str,
        project_id: Optional[int],
        *,
        applies_to: str,
    ) -> None:
        if not self.db or not project_id:
            return
        try:
            policy_service = PolicyService(self.context, self.db)
            effective = policy_service.resolve_effective_policy(
                project_id,
                repo_root=Path(project_path),
                include_repo_local=True,
            )
            clarifier = ClarifierService(self.context, self.db)
            clarifier.ensure_from_policy(
                project_id=project_id,
                policy=effective.policy,
                applies_to=applies_to,
            )
        except Exception as exc:
            self.logger.warning(
                "policy_clarifications_persist_failed",
                extra=self.log_extra(project_id=project_id, path=project_path, error=str(exc)),
            )

    def _ensure_runtime_dir(self, spec_dir: Path, feature_name: str) -> None:
        runtime_dir = spec_dir / "_runtime"
        runtime_dir.mkdir(exist_ok=True)
        (runtime_dir / "context.md").write_text(f"# Execution Context: {feature_name}\n\n")
        (runtime_dir / "log.md").write_text(f"# Execution Log: {feature_name}\n\n")
        (runtime_dir / "runs").mkdir(exist_ok=True)

    def _infer_feature_name(self, branch_name: Optional[str]) -> str:
        if not branch_name:
            return "feature"
        parts = branch_name.split("-", 1)
        if len(parts) == 2:
            return parts[1]
        return branch_name

    def _append_clarifications(
        self,
        content: str,
        clarifications: List[Dict[str, str]],
    ) -> tuple[str, int]:
        if not clarifications:
            return content, 0

        date_str = datetime.utcnow().date().isoformat()
        header = "## Clarifications"
        session_header = f"### Session {date_str}"

        updated = content.rstrip() + "\n\n"
        if header not in updated:
            updated += f"{header}\n\n"
        if session_header not in updated:
            updated += f"{session_header}\n"

        added = 0
        for entry in clarifications:
            question = entry.get("question", "").strip()
            answer = entry.get("answer", "").strip()
            if not question and not answer:
                continue
            updated += f"- Q: {question or 'Note'} -> A: {answer}\n"
            added += 1

        return updated + "\n", added

    def _resolve_speckit_source(self) -> Optional[Path]:
        """Resolve upstream SpecKit source directory if vendored."""
        if self.speckit_source_path and self.speckit_source_path.exists():
            return self.speckit_source_path

        env_path = os.environ.get("DEVGODZILLA_SPECKIT_SOURCE")
        if env_path:
            candidate = Path(env_path).expanduser()
            if candidate.exists():
                return candidate

        try:
            repo_root = Path(__file__).resolve().parents[2]
        except IndexError:
            return None

        candidate = repo_root / "Origins" / "spec-kit"
        return candidate if candidate.exists() else None

    def _copy_dir_contents(self, source: Path, destination: Path) -> None:
        """Copy directory contents without overwriting existing files."""
        for path in source.rglob("*"):
            if path.is_dir():
                continue
            relative = path.relative_to(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(path, target)

    def _copy_file_if_missing(self, source: Path, destination: Path) -> None:
        """Copy a file to destination if it does not already exist."""
        if destination.exists():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _resolve_specs_dir(self, project_path: str) -> Path:
        """
        Resolve the primary specs directory for new artifacts.

        Uses `specs/` for all SpecKit artifacts.
        """
        root = Path(project_path)
        return root / "specs"

    def _list_specs_dirs(self, project_path: str) -> List[Path]:
        """Return spec directories using the canonical location only."""
        root = Path(project_path)
        return [root / "specs"]
