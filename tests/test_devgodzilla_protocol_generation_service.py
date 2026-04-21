"""
Tests for ProtocolGenerationService.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.protocol_generation import (
    ProtocolGenerationService,
    ProtocolGenerationResult,
    _render_prompt,
)
from devgodzilla.config import load_config
from devgodzilla.engines import EngineRegistry, EngineNotFoundError


class TestProtocolGenerationService:
    """Tests for ProtocolGenerationService."""

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
    def worktree_root(self, tmp_path: Path):
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").mkdir()
        (worktree / ".protocols").mkdir()
        return worktree

    @pytest.fixture
    def prompt_path(self, tmp_path: Path):
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        prompt_file = prompts / "protocol-generate.prompt.md"
        prompt_file.write_text(
            "# Protocol Generation\n\n"
            "Name: {{PROTOCOL_NAME}}\n"
            "Description: {{PROTOCOL_DESCRIPTION}}\n"
            "Steps: {{STEP_COUNT}}\n"
        )
        return prompt_file

    @pytest.fixture
    def generation_service(self, context: ServiceContext):
        return ProtocolGenerationService(context)

    # ==================== _render_prompt Tests ====================

    def test_render_prompt_basic(self):
        """Test basic prompt rendering."""
        template = "Name: {{PROTOCOL_NAME}}, Steps: {{STEP_COUNT}}"
        result = _render_prompt(
            template,
            protocol_name="test-protocol",
            description="Test description",
            step_count=5,
        )
        assert "test-protocol" in result
        assert "5" in result

    def test_render_prompt_with_description(self):
        """Test prompt rendering with description."""
        template = "{{PROTOCOL_NAME}}: {{PROTOCOL_DESCRIPTION}}"
        result = _render_prompt(
            template,
            protocol_name="auth-feature",
            description="Add OAuth authentication",
            step_count=3,
        )
        assert "auth-feature" in result
        assert "Add OAuth authentication" in result

    def test_render_prompt_missing_placeholders(self):
        """Test prompt rendering when some placeholders are missing in template."""
        template = "Fixed template with no placeholders"
        result = _render_prompt(
            template,
            protocol_name="name",
            description="desc",
            step_count=1,
        )
        assert result == "Fixed template with no placeholders"

    def test_render_prompt_appends_workflow_context_when_placeholder_missing(self):
        """Workflow context should still be appended when the template lacks an explicit placeholder."""
        template = "Fixed template"
        result = _render_prompt(
            template,
            protocol_name="name",
            description="desc",
            step_count=1,
            workflow_context="## Effective Policy\n\n- Pack: default@1.0",
        )
        assert result.startswith("Fixed template")
        assert "## Effective Policy" in result

    # ==================== generate Tests ====================

    def test_generate_success(self, generation_service, worktree_root, prompt_path):
        """Test successful protocol generation."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="Generated protocol",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test-protocol",
                description="Test protocol description",
                step_count=3,
                prompt_path=prompt_path,
                strict_outputs=False,  # Don't require output files in test
            )

        assert result.success is True
        assert result.engine_id == "opencode"
        assert result.model == "test-model"
        assert result.protocol_root.name == "test-protocol"

    def test_generate_uses_agent_config_default_model_when_project_provided(self, monkeypatch, tmp_path: Path, worktree_root, prompt_path):
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    enabled: true
    default_model: kimi-for-coding/kimi-k2-thinking
defaults:
  planning: opencode
""".strip(),
            encoding="utf-8",
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_OPENCODE_MODEL", raising=False)

        config = load_config()
        generation_service = ProtocolGenerationService(ServiceContext(config=config))

        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "engine-default-model"
        mock_engine.execute.return_value = MagicMock(success=True, stdout="", stderr="", error=None)

        with patch.object(EngineRegistry, "get", return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test-protocol",
                description="Test protocol description",
                step_count=3,
                prompt_path=prompt_path,
                project_id=1,
                strict_outputs=False,
            )

        assert result.success is True
        assert result.model == "kimi-for-coding/kimi-k2-thinking"
        req = mock_engine.execute.call_args[0][0]
        assert req.model == "kimi-for-coding/kimi-k2-thinking"

    def test_generate_prompt_not_found(self, generation_service, worktree_root):
        """Test error when prompt file not found."""
        result = generation_service.generate(
            worktree_root=worktree_root,
            protocol_name="test",
            description="desc",
            prompt_path=Path("/nonexistent/prompt.md"),
        )

        assert result.success is False
        assert "Prompt not found" in result.error

    def test_generate_engine_not_registered(self, generation_service, worktree_root, prompt_path):
        """Test error when engine not registered."""
        with patch.object(EngineRegistry, 'get', side_effect=EngineNotFoundError("not found")):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                engine_id="nonexistent",
                prompt_path=prompt_path,
            )

        assert result.success is False
        assert "Engine not registered" in result.error

    def test_generate_engine_unavailable(self, generation_service, worktree_root, prompt_path):
        """Test error when engine is unavailable."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = False

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                engine_id="unavailable-engine",
                prompt_path=prompt_path,
            )

        assert result.success is False
        assert "Engine unavailable" in result.error

    def test_generate_engine_execution_failure(self, generation_service, worktree_root, prompt_path):
        """Test handling engine execution failure."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=False,
            stdout="",
            stderr="Error",
            error="Execution failed",
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                prompt_path=prompt_path,
                strict_outputs=False,  # Don't require output files in test
            )

        assert result.success is False
        assert result.error == "Execution failed"

    def test_generate_strict_outputs_missing_plan(self, generation_service, worktree_root, prompt_path):
        """Test strict mode fails when plan.md missing."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                step_count=3,
                prompt_path=prompt_path,
                strict_outputs=True,
            )

        # Should fail because plan.md and step files weren't created
        assert result.success is False
        assert "Missing protocol outputs" in result.error

    def test_generate_non_strict_outputs(self, generation_service, worktree_root, prompt_path):
        """Test non-strict mode passes even without outputs."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                step_count=3,
                prompt_path=prompt_path,
                strict_outputs=False,
            )

        assert result.success is True

    def test_generate_custom_model(self, generation_service, worktree_root, prompt_path):
        """Test using custom model."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "default-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                prompt_path=prompt_path,
                model="custom-model",
                strict_outputs=False,
            )

        assert result.model == "custom-model"

        # Verify custom model was used in request
        call_args = mock_engine.execute.call_args
        request = call_args[0][0]
        assert request.model == "custom-model"

    def test_generate_with_created_files(self, generation_service, worktree_root, prompt_path):
        """Test tracking created files."""
        # Pre-create some expected files
        protocol_root = worktree_root / ".protocols" / "test"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan")
        (protocol_root / "step-01-setup.md").write_text("# Setup")
        (protocol_root / "step-02-implement.md").write_text("# Implement")

        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                prompt_path=prompt_path,
                strict_outputs=False,
            )

        assert len(result.created_files) == 3
        names = [f.name for f in result.created_files]
        assert "plan.md" in names
        assert "step-01-setup.md" in names
        assert "step-02-implement.md" in names

    def test_generate_timeout_parameter(self, generation_service, worktree_root, prompt_path):
        """Test timeout parameter is passed correctly."""
        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            generation_service.generate(
                worktree_root=worktree_root,
                protocol_name="test",
                description="desc",
                prompt_path=prompt_path,
                timeout_seconds=600,
                strict_outputs=False,
            )

        # Verify timeout was passed
        call_args = mock_engine.execute.call_args
        request = call_args[0][0]
        assert request.timeout == 600

    def test_generate_expands_user_path(self, generation_service, tmp_path, prompt_path):
        """Test that paths are expanded properly."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").mkdir()

        mock_engine = MagicMock()
        mock_engine.check_availability.return_value = True
        mock_engine.metadata.default_model = "test-model"
        mock_engine.execute.return_value = MagicMock(
            success=True,
            stdout="",
            stderr="",
            error=None,
        )

        with patch.object(EngineRegistry, 'get', return_value=mock_engine):
            result = generation_service.generate(
                worktree_root=worktree,
                protocol_name="test",
                description="desc",
                prompt_path=prompt_path,
                strict_outputs=False,
            )

        assert result.worktree_root.is_absolute()

    # ==================== ProtocolGenerationResult Tests ====================

    def test_protocol_generation_result_dataclass(self):
        """Test ProtocolGenerationResult dataclass."""
        result = ProtocolGenerationResult(
            success=True,
            engine_id="test-engine",
            model="test-model",
            worktree_root=Path("/tmp/worktree"),
            protocol_root=Path("/tmp/worktree/.protocols/test"),
            prompt_path=Path("/tmp/prompt.md"),
            created_files=[Path("/tmp/file1.md"), Path("/tmp/file2.md")],
            stdout="output",
            stderr="",
            error=None,
        )

        assert result.success is True
        assert result.engine_id == "test-engine"
        assert len(result.created_files) == 2
