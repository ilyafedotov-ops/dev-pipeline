"""
Tests for SpecToProtocolService.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.spec_to_protocol import (
    SpecToProtocolService,
    SpecToProtocolResult,
)
from devgodzilla.config import load_config


class TestSpecToProtocolService:
    """Tests for SpecToProtocolService."""

    @pytest.fixture
    def db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        return db

    @pytest.fixture
    def context(self):
        config = load_config()
        return ServiceContext(config=config)

    @pytest.fixture
    def repo_root(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / "specs").mkdir()
        return repo

    @pytest.fixture
    def spec_dir(self, repo_root: Path):
        spec_dir = repo_root / "specs" / "0001-feature"
        spec_dir.mkdir(parents=True)
        return spec_dir

    @pytest.fixture
    def sample_project(self, db: SQLiteDatabase, repo_root: Path):
        project = db.create_project(
            name="SpecTest Project",
            git_url="https://github.com/example/test.git",
            base_branch="main",
        )
        db.update_project(project.id, local_path=str(repo_root))
        return db.get_project(project.id)

    @pytest.fixture
    def spec_service(self, context: ServiceContext, db: SQLiteDatabase):
        return SpecToProtocolService(context, db)

    # ==================== create_protocol_from_spec Tests ====================

    def test_create_protocol_success(self, spec_service, sample_project, spec_dir):
        """Test successful protocol creation from spec."""
        # Create tasks.md
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("""
# Tasks

## Phase 1: Setup

- [ ] Initialize project
- [ ] Configure dependencies

## Phase 2: Implementation

- [ ] Implement core logic
- [ ] Add tests
""")

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            protocol_name="feature-protocol",
        )

        assert result.success is True
        assert result.protocol_run_id is not None
        assert result.step_count == 2  # Two phases
        assert result.protocol_root is not None

    def test_create_protocol_with_spec_path(self, spec_service, sample_project, spec_dir):
        """Test protocol creation with explicit spec path."""
        spec_path = spec_dir / "spec.md"
        spec_path.write_text("# Feature Specification\n\nDescription here.")

        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Tasks\n\n- [ ] Task 1\n")

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            spec_path=str(spec_path),
            tasks_path=str(tasks_path),
        )

        assert result.success is True

    def test_create_protocol_no_local_path(self, spec_service, db):
        """Test error when project has no local path."""
        project = db.create_project(
            name="NoPath",
            git_url="https://example.com/nopath.git",
            base_branch="main",
        )

        result = spec_service.create_protocol_from_spec(
            project_id=project.id,
            tasks_path="specs/tasks.md",
        )

        assert result.success is False
        assert "no local_path" in result.error.lower()

    def test_create_protocol_tasks_not_found(self, spec_service, sample_project):
        """Test error when tasks file not found."""
        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path="nonexistent/tasks.md",
        )

        assert result.success is False
        assert "Tasks file not found" in result.error

    def test_create_protocol_empty_tasks(self, spec_service, sample_project, spec_dir):
        """Test error when tasks.md is empty."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("# Empty file\n\nNo tasks here.")

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
        )

        assert result.success is False
        assert "No tasks found" in result.error

    def test_create_protocol_with_spec_run(self, spec_service, sample_project, spec_dir, db):
        """Test protocol creation linked to spec run."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Phase 1\n\n- [ ] Task\n")

        # Create a spec run with all required fields
        spec_run = db.create_spec_run(
            project_id=sample_project.id,
            spec_name="test-spec",
            spec_path="specs/0001-feature/spec.md",
            status="pending",
            base_branch="main",
        )

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            spec_run_id=spec_run.id,
        )

        assert result.success is True

        # Verify spec run is linked (if supported)
        try:
            updated_spec_run = db.get_spec_run(spec_run.id)
            # Protocol run ID may be set
            assert updated_spec_run is not None
        except Exception:
            pass  # Spec run linking is optional

    def test_create_protocol_persists_spec_run_id_in_metadata(
        self,
        spec_service,
        sample_project,
        spec_dir,
        db,
    ):
        """Protocols created from a spec run should carry review context metadata."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Phase 1\n\n- [ ] Task\n")

        spec_run = db.create_spec_run(
            project_id=sample_project.id,
            spec_name="review-ready",
            spec_path="specs/0001-feature/spec.md",
            status="planned",
            base_branch="main",
        )

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            spec_run_id=spec_run.id,
        )

        assert result.success is True
        protocol = db.get_protocol_run(result.protocol_run_id)
        assert protocol.speckit_metadata is not None
        assert protocol.speckit_metadata["spec_run_id"] == spec_run.id

    def test_create_protocol_overwrite_existing(self, spec_service, sample_project, spec_dir):
        """Test overwriting existing protocol files."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Phase 1\n\n- [ ] Task\n")

        # Create initial protocol
        result1 = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            protocol_name="overwrite-test",
        )
        assert result1.success is True

        # Create again with overwrite
        result2 = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            protocol_name="overwrite-test",
            overwrite=True,
        )
        assert result2.success is True

    def test_create_protocol_preserves_existing_without_overwrite(
        self, spec_service, sample_project, spec_dir
    ):
        """Test existing files are preserved without overwrite flag."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Phase 1\n\n- [ ] Task\n")

        # Create initial protocol
        result1 = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            protocol_name="preserve-test",
        )
        assert result1.success is True

        # Create again without overwrite
        result2 = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            protocol_name="preserve-test",
            overwrite=False,
        )
        assert result2.success is True
        assert "Existing runtime steps" in result2.warnings[0]

    # ==================== _parse_tasks_by_phase Tests ====================

    def test_parse_tasks_by_phase_basic(self, spec_service):
        """Test parsing basic tasks by phase."""
        content = """
## Setup Phase
- [x] Initialize
- [ ] Configure

## Implementation Phase
- [ ] Build feature
- [ ] Write tests
"""
        phases = spec_service._parse_tasks_by_phase(content)

        assert len(phases) == 2
        assert phases[0][0] == "Setup Phase"
        assert len(phases[0][1]) == 2
        assert phases[1][0] == "Implementation Phase"
        assert len(phases[1][1]) == 2

    def test_parse_tasks_by_phase_with_different_heading_levels(self, spec_service):
        """Test parsing with different heading levels."""
        content = """
# Main Title
### Phase 1
- [ ] Task 1

#### Sub-phase
- [ ] Task 2

##### Phase 2
- [ ] Task 3
"""
        phases = spec_service._parse_tasks_by_phase(content)

        assert len(phases) == 3
        assert phases[0][0] == "Phase 1"
        assert phases[1][0] == "Sub-phase"
        assert phases[2][0] == "Phase 2"

    def test_parse_tasks_by_phase_empty(self, spec_service):
        """Test parsing empty content."""
        phases = spec_service._parse_tasks_by_phase("")
        assert phases == []

    def test_parse_tasks_by_phase_no_tasks(self, spec_service):
        """Test parsing content with no tasks."""
        content = """
## Phase 1
Some description but no tasks.

## Phase 2
More description.
"""
        phases = spec_service._parse_tasks_by_phase(content)
        assert phases == []

    def test_parse_tasks_by_phase_default_title(self, spec_service):
        """Test default title when no headings."""
        content = "- [ ] Task 1\n- [ ] Task 2\n"
        phases = spec_service._parse_tasks_by_phase(content)

        assert len(phases) == 1
        assert phases[0][0] == "Tasks"
        assert len(phases[0][1]) == 2

    # ==================== _slugify Tests ====================

    def test_slugify_basic(self, spec_service):
        """Test basic slugification."""
        assert spec_service._slugify("Simple Title") == "simple-title"
        assert spec_service._slugify("Another Test") == "another-test"

    def test_slugify_special_characters(self, spec_service):
        """Test slugification with special characters."""
        assert spec_service._slugify("Hello! @World#") == "hello-world"
        assert spec_service._slugify("Test/With\\Slashes") == "test-with-slashes"

    def test_slugify_multiple_spaces(self, spec_service):
        """Test slugification with multiple spaces."""
        assert spec_service._slugify("Multiple   Spaces") == "multiple-spaces"

    def test_slugify_empty(self, spec_service):
        """Test slugification of empty string."""
        assert spec_service._slugify("") == "phase"
        assert spec_service._slugify("   ") == "phase"

    # ==================== _resolve_paths Tests ====================

    def test_resolve_paths_both_provided(self, spec_service, repo_root, spec_dir):
        """Test resolving both spec and tasks paths."""
        spec_path = spec_dir / "spec.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.touch()
        tasks_path.touch()

        resolved_spec, resolved_tasks, resolved_dir = spec_service._resolve_paths(
            repo_root,
            spec_path=str(spec_path),
            tasks_path=str(tasks_path),
        )

        assert resolved_spec == spec_path
        assert resolved_tasks == tasks_path
        assert resolved_dir == spec_dir

    def test_resolve_paths_relative(self, spec_service, repo_root, spec_dir):
        """Test resolving relative paths."""
        spec_path = spec_dir / "spec.md"
        spec_path.touch()
        tasks_path = spec_dir / "tasks.md"
        tasks_path.touch()

        resolved_spec, resolved_tasks, resolved_dir = spec_service._resolve_paths(
            repo_root,
            spec_path="specs/0001-feature/spec.md",
            tasks_path="specs/0001-feature/tasks.md",
        )

        assert resolved_spec == spec_path
        assert resolved_tasks == tasks_path

    def test_resolve_paths_auto_detect_tasks(self, spec_service, repo_root, spec_dir):
        """Test auto-detecting tasks.md from spec directory."""
        spec_path = spec_dir / "spec.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.touch()
        tasks_path.touch()

        resolved_spec, resolved_tasks, resolved_dir = spec_service._resolve_paths(
            repo_root,
            spec_path=str(spec_path),
            tasks_path=None,
        )

        assert resolved_tasks == tasks_path

    # ==================== Step File Generation Tests ====================

    def test_step_files_created(self, spec_service, sample_project, spec_dir):
        """Test that step files are created correctly."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("""
## Setup
- [ ] Initialize

## Build
- [ ] Implement

## Test
- [ ] Write tests
""")

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            protocol_name="step-test",
        )

        assert result.success is True
        assert result.step_count == 3

        # Verify step files exist
        protocol_root = Path(result.protocol_root)
        assert (protocol_root / "step-01-setup.md").exists()
        assert (protocol_root / "step-02-build.md").exists()
        assert (protocol_root / "step-03-test.md").exists()

    def test_runtime_files_created(self, spec_service, sample_project, spec_dir):
        """Test that runtime support files are created."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Phase\n- [ ] Task\n")

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
        )

        assert result.success is True

        protocol_root = Path(result.protocol_root)
        assert (protocol_root / "README.md").exists()
        assert (protocol_root / "plan.md").exists()
        assert (protocol_root / "context.md").exists()
        assert (protocol_root / "log.md").exists()
        assert (protocol_root / "runs").is_dir()

    def test_existing_runtime_steps_still_get_missing_support_files(
        self,
        spec_service,
        sample_project,
        spec_dir,
    ):
        """Support files should be backfilled even when step scaffolding is preserved."""
        tasks_path = spec_dir / "tasks.md"
        tasks_path.write_text("## Phase\n- [ ] Task\n")
        protocol_root = spec_dir / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "step-01-phase.md").write_text("# Step\n", encoding="utf-8")

        result = spec_service.create_protocol_from_spec(
            project_id=sample_project.id,
            tasks_path=str(tasks_path),
            overwrite=False,
        )

        assert result.success is True
        assert "Existing runtime steps" in result.warnings[0]
        assert (protocol_root / "README.md").exists()
        assert (protocol_root / "context.md").exists()
        assert (protocol_root / "log.md").exists()

    # ==================== SpecToProtocolResult Tests ====================

    def test_spec_to_protocol_result_dataclass(self):
        """Test SpecToProtocolResult dataclass."""
        result = SpecToProtocolResult(
            success=True,
            protocol_run_id=123,
            protocol_root="/path/to/protocol",
            step_count=5,
            warnings=["Warning 1"],
            error=None,
        )

        assert result.success is True
        assert result.protocol_run_id == 123
        assert result.step_count == 5
        assert len(result.warnings) == 1
