"""
Tests for GeminiEngine.

Validates the CLIEngine-based GeminiEngine adapter using the real
devgodzilla.engines.interface types (EngineRequest, EngineResult, etc.).
"""

from unittest.mock import MagicMock, patch

import pytest

from devgodzilla.engines.gemini import GeminiEngine, register_gemini_engine
from devgodzilla.engines.interface import (
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(**overrides):
    """Build a minimal EngineRequest with sensible defaults."""
    defaults = dict(
        project_id=1,
        protocol_run_id=1,
        step_run_id=1,
        prompt_text="Write a hello world function",
        working_dir="/tmp",
    )
    defaults.update(overrides)
    return EngineRequest(**defaults)


# ---------------------------------------------------------------------------
# Metadata & Initialization
# ---------------------------------------------------------------------------

class TestGeminiEngineMetadata:
    """Tests for GeminiEngine metadata and initialization."""

    def test_default_initialization(self):
        engine = GeminiEngine()
        assert engine._default_model == "gemini-2.5-pro"
        assert engine._default_timeout == 300

    def test_custom_model(self):
        engine = GeminiEngine(default_model="gemini-2.5-flash")
        assert engine._default_model == "gemini-2.5-flash"

    def test_custom_timeout(self):
        engine = GeminiEngine(default_timeout=600)
        assert engine._default_timeout == 600

    def test_metadata_id(self):
        engine = GeminiEngine()
        assert engine.metadata.id == "gemini-cli"

    def test_metadata_display_name(self):
        engine = GeminiEngine()
        assert engine.metadata.display_name == "Gemini CLI"

    def test_metadata_kind(self):
        engine = GeminiEngine()
        assert engine.metadata.kind == EngineKind.CLI

    def test_metadata_default_model(self):
        engine = GeminiEngine(default_model="gemini-2.5-flash")
        assert engine.metadata.default_model == "gemini-2.5-flash"

    def test_metadata_description(self):
        engine = GeminiEngine()
        assert engine.metadata.description is not None
        assert "Gemini" in engine.metadata.description

    def test_metadata_capabilities(self):
        engine = GeminiEngine()
        caps = engine.metadata.capabilities
        assert "multimodal" in caps
        assert "long-context" in caps
        assert "execute" in caps


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

class TestGeminiEngineAvailability:
    """Tests for check_availability method."""

    @patch("shutil.which")
    def test_available_when_installed_with_key(self, mock_which):
        mock_which.return_value = "/usr/local/bin/gemini"
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=False):
            engine = GeminiEngine()
            assert engine.check_availability() is True

    @patch("shutil.which")
    def test_available_with_gemini_api_key(self, mock_which):
        mock_which.return_value = "/usr/local/bin/gemini"
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False):
            engine = GeminiEngine()
            assert engine.check_availability() is True

    @patch("shutil.which")
    def test_available_with_assume_auth(self, mock_which):
        mock_which.return_value = "/usr/local/bin/gemini"
        with patch.dict("os.environ", {"DEVGODZILLA_ASSUME_AGENT_AUTH": "true"}, clear=False):
            # Remove API keys to ensure ASSUME_AGENT_AUTH is the reason
            env = {"DEVGODZILLA_ASSUME_AGENT_AUTH": "true"}
            with patch.dict("os.environ", env, clear=True):
                engine = GeminiEngine()
                assert engine.check_availability() is True

    @patch("shutil.which")
    def test_unavailable_when_not_installed(self, mock_which):
        mock_which.return_value = None
        engine = GeminiEngine()
        assert engine.check_availability() is False

    @patch("shutil.which")
    def test_unavailable_when_no_api_key(self, mock_which):
        mock_which.return_value = "/usr/local/bin/gemini"
        # Clear all relevant env vars
        with patch.dict("os.environ", {}, clear=True):
            engine = GeminiEngine()
            assert engine.check_availability() is False


# ---------------------------------------------------------------------------
# Command Building
# ---------------------------------------------------------------------------

class TestGeminiEngineCommandBuilding:
    """Tests for _build_command method."""

    def test_basic_command_structure(self):
        engine = GeminiEngine()
        req = _make_request()
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "gemini"
        assert cmd[-1] == "-"  # stdin prompt

    def test_includes_model_flag(self):
        engine = GeminiEngine()
        req = _make_request(model="gemini-2.5-flash")
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "gemini-2.5-flash"

    def test_command_name(self):
        engine = GeminiEngine()
        assert engine._get_command_name() == "gemini"


# ---------------------------------------------------------------------------
# Execution (via CLIEngine._run)
# ---------------------------------------------------------------------------

class TestGeminiEngineExecute:
    """Tests for execute/plan/qa methods through CLIEngine._run."""

    @patch("devgodzilla.engines.cli_adapter.run_cli_command")
    def test_execute_success(self, mock_run_cli):
        mock_run_cli.return_value = EngineResult(
            success=True,
            stdout="Function created successfully",
            stderr="",
            metadata={"cmd": "gemini"},
        )

        engine = GeminiEngine()
        req = _make_request()
        result = engine.execute(req)

        assert result.success is True
        assert "Function created" in result.stdout
        # CLIEngine._run adds engine_id to metadata
        assert result.metadata.get("engine_id") == "gemini-cli"

    @patch("devgodzilla.engines.cli_adapter.run_cli_command")
    def test_execute_failure(self, mock_run_cli):
        mock_run_cli.return_value = EngineResult(
            success=False,
            stdout="",
            stderr="Error: something went wrong",
            error="Command failed",
            metadata={"cmd": "gemini"},
        )

        engine = GeminiEngine()
        req = _make_request()
        result = engine.execute(req)

        assert result.success is False
        assert result.error is not None

    @patch("devgodzilla.engines.cli_adapter.run_cli_command")
    def test_execute_passes_cwd(self, mock_run_cli):
        mock_run_cli.return_value = EngineResult(
            success=True, stdout="OK", stderr="", metadata={"cmd": "gemini"},
        )

        engine = GeminiEngine()
        req = _make_request(working_dir="/custom/path")
        engine.execute(req)

        # run_cli_command should have been called with cwd pointing to working_dir
        call_kwargs = mock_run_cli.call_args
        assert call_kwargs is not None

    @patch("devgodzilla.engines.cli_adapter.run_cli_command")
    def test_execute_with_custom_model(self, mock_run_cli):
        mock_run_cli.return_value = EngineResult(
            success=True, stdout="OK", stderr="", metadata={"cmd": "gemini"},
        )

        engine = GeminiEngine()
        req = _make_request(model="gemini-2.5-flash")
        result = engine.execute(req)

        assert result.success is True
        # Verify the command included --model gemini-2.5-flash
        call_args = mock_run_cli.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("cmd", [])
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "gemini-2.5-flash"

    @patch("devgodzilla.engines.cli_adapter.run_cli_command")
    def test_plan_uses_full_access(self, mock_run_cli):
        mock_run_cli.return_value = EngineResult(
            success=True, stdout="Plan done", stderr="", metadata={"cmd": "gemini"},
        )

        engine = GeminiEngine()
        req = _make_request()
        result = engine.plan(req)

        assert result.success is True
        # Verify sandbox was full-access
        assert result.metadata.get("sandbox") == "full-access"

    @patch("devgodzilla.engines.cli_adapter.run_cli_command")
    def test_qa_uses_read_only(self, mock_run_cli):
        mock_run_cli.return_value = EngineResult(
            success=True, stdout="QA done", stderr="", metadata={"cmd": "gemini"},
        )

        engine = GeminiEngine()
        req = _make_request()
        result = engine.qa(req)

        assert result.success is True
        assert result.metadata.get("sandbox") == "read-only"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestGeminiEngineRegistration:
    """Tests for register_gemini_engine helper."""

    def test_register_returns_engine(self):
        with patch("devgodzilla.engines.registry.get_registry"):
            engine = GeminiEngine()
            assert isinstance(engine, GeminiEngine)
            assert isinstance(engine.metadata, EngineMetadata)
