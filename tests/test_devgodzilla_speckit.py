"""
Tests for DevGodzilla SpecKit Integration.

Tests the SpecificationService including initialization, spec generation,
planning, and task list creation.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from devgodzilla.services.specification import (
    SpecificationService,
    SpecKitResult,
    SpecifyResult,
    PlanResult,
    TasksResult,
)
from devgodzilla.services.base import ServiceContext


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace for testing."""
    return tmp_path


@pytest.fixture
def initialized_workspace(tmp_path):
    """Create an initialized SpecKit workspace."""
    specify_dir = tmp_path / ".specify"
    specify_dir.mkdir()
    (specify_dir / "memory").mkdir()
    (specify_dir / "templates").mkdir()
    (tmp_path / "specs").mkdir()
    (specify_dir / "memory" / "constitution.md").write_text("# Test Constitution\n")
    (specify_dir / "templates" / "spec-template.md").write_text("# {{ title }}\n{{ description }}")
    (specify_dir / "templates" / "plan-template.md").write_text("# {{ title }}\n{{ description }}")
    (specify_dir / "templates" / "tasks-template.md").write_text("# {{ title }}\n- [ ] Task 1")
    return tmp_path


@pytest.fixture
def service_context():
    """Create a mock service context."""
    config = Mock()
    config.engine_defaults = {"planning": "dummy"}
    return ServiceContext(config=config)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = Mock()

    mock_project = Mock()
    mock_project.id = 1
    mock_project.local_path = "/tmp/repo"
    mock_project.constitution_version = None
    mock_project.constitution_hash = None

    db.get_project.return_value = mock_project
    db.update_project.return_value = None

    return db


@pytest.fixture
def service(service_context):
    """Create a SpecificationService without DB."""
    return SpecificationService(service_context)


@pytest.fixture
def service_with_db(service_context, mock_db):
    """Create a SpecificationService with mock DB."""
    return SpecificationService(service_context, mock_db)


class TestSpecificationServiceInit:
    """Tests for SpecificationService.init_project()"""

    def test_init_creates_directory_structure(self, service, workspace):
        """Test that init creates the .specify directory structure."""
        result = service.init_project(str(workspace))

        assert result.success
        assert result.spec_path == str(workspace / ".specify")
        assert (workspace / ".specify" / "memory").exists()
        assert (workspace / ".specify" / "templates").exists()
        assert (workspace / "specs").exists()

    def test_init_creates_default_constitution(self, service, workspace):
        """Test that init creates default constitution."""
        result = service.init_project(str(workspace))

        assert result.success
        constitution_path = workspace / ".specify" / "memory" / "constitution.md"
        assert constitution_path.exists()
        content = constitution_path.read_text()
        assert "Constitution" in content
        assert ("Safety First" in content) or ("[PRINCIPLE_1_NAME]" in content)

    def test_init_creates_templates(self, service, workspace):
        """Test that init creates default templates."""
        result = service.init_project(str(workspace))

        assert result.success
        templates_dir = workspace / ".specify" / "templates"
        assert (templates_dir / "spec-template.md").exists()
        assert (templates_dir / "plan-template.md").exists()
        assert (templates_dir / "tasks-template.md").exists()
        assert (templates_dir / "checklist-template.md").exists()

    def test_init_with_custom_constitution(self, service, workspace):
        """Test init with custom constitution content."""
        custom_content = "# Custom Constitution\n\nMy rules here."
        result = service.init_project(str(workspace), constitution_content=custom_content)

        assert result.success
        constitution_path = workspace / ".specify" / "memory" / "constitution.md"
        assert constitution_path.read_text() == custom_content

    def test_init_returns_constitution_hash(self, service, workspace):
        """Test that init returns constitution hash."""
        result = service.init_project(str(workspace))

        assert result.success
        assert result.constitution_hash is not None
        assert len(result.constitution_hash) == 16  # SHA256 truncated to 16 chars

    def test_init_existing_directory_returns_warning(self, service, initialized_workspace):
        """Test that init on existing directory returns warning."""
        result = service.init_project(str(initialized_workspace))

        assert result.success
        assert "already exists" in result.warnings[0]

    def test_init_updates_db_with_constitution(self, service_with_db, mock_db, workspace):
        """Test that init updates DB with constitution hash."""
        result = service_with_db.init_project(str(workspace), project_id=1)

        assert result.success
        mock_db.update_project.assert_called_once()
        call_args = mock_db.update_project.call_args
        assert call_args[0][0] == 1  # project_id
        assert "constitution_version" in call_args[1]
        assert "constitution_hash" in call_args[1]


class TestSpecificationServiceConstitution:
    """Tests for constitution management."""

    def test_get_constitution(self, service, initialized_workspace):
        """Test getting constitution content."""
        content = service.get_constitution(str(initialized_workspace))

        assert content is not None
        assert "Test Constitution" in content

    def test_get_constitution_not_found(self, service, workspace):
        """Test getting constitution when not initialized."""
        content = service.get_constitution(str(workspace))

        assert content is None

    def test_save_constitution(self, service, initialized_workspace):
        """Test saving constitution content."""
        new_content = "# Updated Constitution\n\nNew rules."
        result = service.save_constitution(str(initialized_workspace), new_content)

        assert result.success
        saved_content = service.get_constitution(str(initialized_workspace))
        assert saved_content == new_content

    def test_save_constitution_creates_directory(self, service, workspace):
        """Test that save_constitution creates directory if needed."""
        new_content = "# New Constitution\n"
        result = service.save_constitution(str(workspace), new_content)

        assert result.success
        constitution_path = workspace / ".specify" / "memory" / "constitution.md"
        assert constitution_path.exists()


class TestSpecificationServiceSpecify:
    """Tests for SpecificationService.run_specify()"""

    def test_specify_creates_spec_directory(self, service, initialized_workspace):
        """Test that specify creates spec directory."""
        result = service.run_specify(
            str(initialized_workspace),
            "Add user authentication with OAuth2",
        )

        assert result.success
        assert result.spec_number == 1
        assert result.feature_name is not None
        assert Path(result.spec_path).exists()

    def test_specify_creates_spec_file(self, service, initialized_workspace):
        """Test that specify creates spec.md file."""
        result = service.run_specify(
            str(initialized_workspace),
            "Add user login functionality",
        )

        assert result.success
        spec_path = Path(result.spec_path)
        assert spec_path.name == "spec.md"
        content = spec_path.read_text()
        assert "Add user login functionality" in content

    def test_specify_with_custom_name(self, service, initialized_workspace):
        """Test specify with custom feature name."""
        result = service.run_specify(
            str(initialized_workspace),
            "Some description here",
            feature_name="custom-feature",
        )

        assert result.success
        assert result.feature_name == "custom-feature"
        assert "custom-feature" in result.spec_path

    def test_specify_increments_spec_number(self, service, initialized_workspace):
        """Test that spec number increments."""
        result1 = service.run_specify(str(initialized_workspace), "First feature")
        result2 = service.run_specify(str(initialized_workspace), "Second feature")

        assert result1.spec_number == 1
        assert result2.spec_number == 2

    def test_specify_sanitizes_feature_name(self, service, initialized_workspace):
        """Test that feature name is sanitized."""
        result = service.run_specify(
            str(initialized_workspace),
            "Add User's Special Feature!!! 123",
        )

        assert result.success
        # Should be lowercase, no special chars
        assert "!" not in result.feature_name
        assert "'" not in result.feature_name


class TestSpecificationServicePlan:
    """Tests for SpecificationService.run_plan()"""

    def test_plan_creates_plan_file(self, service, initialized_workspace):
        """Test that plan creates plan.md file."""
        # First create a spec
        spec_result = service.run_specify(str(initialized_workspace), "Test feature")

        result = service.run_plan(
            str(initialized_workspace),
            spec_result.spec_path,
        )

        assert result.success
        assert Path(result.plan_path).exists()
        assert Path(result.data_model_path).exists()
        assert Path(result.contracts_path).exists()

    def test_plan_creates_data_model(self, service, initialized_workspace):
        """Test that plan creates data-model.md."""
        spec_result = service.run_specify(str(initialized_workspace), "Test feature")
        result = service.run_plan(str(initialized_workspace), spec_result.spec_path)

        assert result.success
        data_model = Path(result.data_model_path).read_text()
        assert "Data Model" in data_model
        assert "Entities" in data_model

    def test_plan_creates_contracts_directory(self, service, initialized_workspace):
        """Test that plan creates contracts directory."""
        spec_result = service.run_specify(str(initialized_workspace), "Test feature")
        result = service.run_plan(str(initialized_workspace), spec_result.spec_path)

        assert result.success
        assert Path(result.contracts_path).is_dir()


class TestSpecificationServiceTasks:
    """Tests for SpecificationService.run_tasks()"""

    def test_tasks_creates_tasks_file(self, service, initialized_workspace):
        """Test that tasks creates tasks.md file."""
        spec_result = service.run_specify(str(initialized_workspace), "Test feature")
        plan_result = service.run_plan(str(initialized_workspace), spec_result.spec_path)

        result = service.run_tasks(
            str(initialized_workspace),
            plan_result.plan_path,
        )

        assert result.success
        assert Path(result.tasks_path).exists()

    def test_tasks_counts_tasks(self, service, initialized_workspace):
        """Test that tasks counts total and parallelizable tasks."""
        spec_result = service.run_specify(str(initialized_workspace), "Test feature")
        plan_result = service.run_plan(str(initialized_workspace), spec_result.spec_path)
        result = service.run_tasks(str(initialized_workspace), plan_result.plan_path)

        assert result.success
        assert result.task_count >= 0
        assert result.parallelizable_count >= 0


class TestSpecificationServiceList:
    """Tests for SpecificationService.list_specs()"""

    def test_list_empty(self, service, initialized_workspace):
        """Test listing specs in empty project."""
        specs = service.list_specs(str(initialized_workspace))

        assert specs == []

    def test_list_with_specs(self, service, initialized_workspace):
        """Test listing specs after creating some."""
        service.run_specify(str(initialized_workspace), "Feature one")
        service.run_specify(str(initialized_workspace), "Feature two")

        specs = service.list_specs(str(initialized_workspace))

        assert len(specs) == 2
        assert all(s["has_spec"] for s in specs)

    def test_list_shows_plan_status(self, service, initialized_workspace):
        """Test that list shows plan status."""
        spec_result = service.run_specify(str(initialized_workspace), "Test feature")
        service.run_plan(str(initialized_workspace), spec_result.spec_path)

        specs = service.list_specs(str(initialized_workspace))

        assert len(specs) == 1
        assert specs[0]["has_spec"]
        assert specs[0]["has_plan"]
        assert not specs[0]["has_tasks"]


class TestSpecificationServiceHelpers:
    """Tests for helper methods."""

    def test_sanitize_feature_name(self, service):
        """Test feature name sanitization."""
        assert service._sanitize_feature_name("Hello World") == "hello-world"
        assert service._sanitize_feature_name("Test!!!") == "test"
        assert service._sanitize_feature_name("A B C D") == "a-b-c-d"
        assert service._sanitize_feature_name("--test--") == "test"

    def test_extract_title(self, service):
        """Test title extraction from markdown."""
        content = "# Feature: My Title\n\nDescription here."
        assert service._extract_title(content) == "My Title"

        content2 = "# Simple Title\n\nDescription."
        assert service._extract_title(content2) == "Simple Title"

    def test_fill_template(self, service):
        """Test template filling."""
        template = "# {{ title }}\n\n{{ description }}"
        result = service._fill_template(template, {
            "title": "Test",
            "description": "Desc",
        })

        assert "# Test" in result
        assert "Desc" in result


class TestSpecKitWorkflow:
    """End-to-end workflow tests."""

    def test_full_spec_workflow(self, service, workspace):
        """Test the complete spec → plan → tasks workflow."""
        # Initialize
        init_result = service.init_project(str(workspace))
        assert init_result.success

        # Create spec
        spec_result = service.run_specify(
            str(workspace),
            "Add user authentication with email and password login",
        )
        assert spec_result.success
        assert spec_result.spec_number == 1

        # Create plan
        plan_result = service.run_plan(str(workspace), spec_result.spec_path)
        assert plan_result.success
        assert plan_result.plan_path is not None

        # Create tasks
        tasks_result = service.run_tasks(str(workspace), plan_result.plan_path)
        assert tasks_result.success
        assert tasks_result.task_count >= 1

        # List specs
        specs = service.list_specs(str(workspace))
        assert len(specs) == 1
        assert specs[0]["has_spec"]
        assert specs[0]["has_plan"]
        assert specs[0]["has_tasks"]
