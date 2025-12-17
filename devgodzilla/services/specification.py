"""
DevGodzilla Specification Service

Manages SpecKit integration, .specify directory structure, and spec-driven
development workflow.

Current implementation is template-based:
- creates `.specify/` structure (constitution + templates)
- generates `feature-spec.md`, `plan.md`, `tasks.md` by filling templates

No external `specify` binary is required for the current code path.
"""

import hashlib
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.services.base import Service, ServiceContext


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


class SpecificationService(Service):
    """
    Manages the SpecKit integration and .specify directory structure.

    Generates SpecKit-style artifacts by filling templates, while handling
    directory management and DB integration internally.
    """

    DOT_SPECIFY = ".specify"
    MEMORY_DIR = "memory"
    TEMPLATES_DIR = "templates"
    SPECS_DIR = "specs"

    def __init__(
        self,
        context: ServiceContext,
        db=None,
        *,
        speckit_cli_path: Optional[str] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.speckit_cli = speckit_cli_path or "specify"

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
        └── specs/

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
            (specify_path / self.SPECS_DIR).mkdir(parents=True, exist_ok=True)

            constitution_path = specify_path / self.MEMORY_DIR / "constitution.md"
            if constitution_content:
                constitution_path.write_text(constitution_content)
            else:
                self._create_default_constitution(constitution_path)

            self._create_default_templates(specify_path / self.TEMPLATES_DIR)

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
                    "specs": str(specify_path / self.SPECS_DIR),
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
            spec_number = self._get_next_spec_number(project_path)
            if not feature_name:
                feature_name = self._sanitize_feature_name(description[:50])

            spec_dir = Path(project_path) / self.DOT_SPECIFY / self.SPECS_DIR / f"{spec_number:03d}-{feature_name}"
            spec_dir.mkdir(parents=True, exist_ok=True)

            spec_path = spec_dir / "feature-spec.md"

            runtime_dir = spec_dir / "_runtime"
            runtime_dir.mkdir(exist_ok=True)
            (runtime_dir / "context.md").write_text(f"# Execution Context: {feature_name}\n\n")
            (runtime_dir / "log.md").write_text(f"# Execution Log: {feature_name}\n\n")
            (runtime_dir / "runs").mkdir(exist_ok=True)
            template = self._load_template(project_path, "spec-template.md")
            spec_content = self._fill_template(template, {
                "title": feature_name,
                "description": description,
                "spec_number": spec_number,
            })
            spec_path.write_text(spec_content)

            self.logger.info("spec_generated", extra={
                **log_extra,
                "spec_number": spec_number,
                "feature_name": feature_name,
            })

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
            spec_dir = Path(spec_path).parent

            plan_path = spec_dir / "plan.md"
            template = self._load_template(project_path, "plan-template.md")

            spec_content = Path(spec_path).read_text()
            title = self._extract_title(spec_content)

            plan_content = self._fill_template(template, {
                "title": title,
                "description": f"Implementation plan for {title}",
            })
            plan_path.write_text(plan_content)

            data_model_path = spec_dir / "data-model.md"
            data_model_path.write_text(f"# Data Model: {title}\n\n## Entities\n\n(To be defined)\n")

            contracts_dir = spec_dir / "contracts"
            contracts_dir.mkdir(exist_ok=True)

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
            plan_dir = Path(plan_path).parent

            tasks_path = plan_dir / "tasks.md"
            template = self._load_template(project_path, "tasks-template.md")

            plan_content = Path(plan_path).read_text()
            title = self._extract_title(plan_content)

            tasks_content = self._fill_template(template, {
                "title": title,
            })
            tasks_path.write_text(tasks_content)

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

    def list_specs(self, project_path: str) -> List[Dict[str, Any]]:
        """
        List all specs in a project.

        Args:
            project_path: Path to the project root

        Returns:
            List of spec metadata dictionaries
        """
        specs_dir = Path(project_path) / self.DOT_SPECIFY / self.SPECS_DIR
        if not specs_dir.exists():
            return []

        specs = []
        for spec_folder in sorted(specs_dir.iterdir()):
            if spec_folder.is_dir():
                # Check for both spec.md and feature-spec.md (run_specify creates feature-spec.md)
                spec_file = spec_folder / "feature-spec.md"
                if not spec_file.exists():
                    spec_file = spec_folder / "spec.md"  # Fallback
                plan_file = spec_folder / "plan.md"
                tasks_file = spec_folder / "tasks.md"

                specs.append({
                    "name": spec_folder.name,
                    "path": str(spec_folder),
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
        specs_dir = Path(project_path) / self.DOT_SPECIFY / self.SPECS_DIR
        if not specs_dir.exists():
            return 1

        existing = [d.name for d in specs_dir.iterdir() if d.is_dir()]
        if not existing:
            return 1

        numbers = []
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
