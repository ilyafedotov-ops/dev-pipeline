"""Tests for all agent adapters."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from devgodzilla.engines.interface import (
    EngineKind,
    EngineRequest,
    SandboxMode,
)


class TestQoderEngine:
    """Tests for Qoder CLI engine adapter."""

    def test_qoder_engine_metadata(self):
        """Test Qoder engine creation and metadata."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine()
        assert engine.metadata.id == "qoder"
        assert engine.metadata.kind == EngineKind.CLI
        assert "code_generation" in engine.metadata.capabilities or "execute" in engine.metadata.capabilities

    def test_qoder_engine_build_command(self, tmp_path: Path):
        """Test Qoder command building."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Create a new module",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "qoder"
        assert "--cwd" in cmd
        assert str(tmp_path) in cmd
        assert "-" in cmd  # Read from stdin

    def test_qoder_engine_build_command_with_model(self, tmp_path: Path):
        """Test Qoder command with custom model."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine(default_model="qoder-pro")

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            model="qoder-custom",
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "qoder-custom"

    def test_qoder_engine_sandbox_modes(self, tmp_path: Path):
        """Test Qoder handles different sandbox modes."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
        )

        # Test different sandbox modes
        for sandbox in [SandboxMode.FULL_ACCESS, SandboxMode.READ_ONLY]:
            cmd = engine._build_command(req, sandbox)
            assert "--sandbox" in cmd

    def test_qoder_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine()
        # Should return False if qoder is not installed
        # (unless environment variables are set)
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_qoder_engine_check_availability_with_auth(self):
        """Test availability check with auth environment variable."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine()
        with patch("shutil.which", return_value="/usr/bin/qoder"), \
             patch.dict(os.environ, {"QODER_API_KEY": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_qoder_engine_check_availability_assume_auth(self):
        """Test availability check with DEVGODZILLA_ASSUME_AGENT_AUTH."""
        from devgodzilla.engines.qoder import QoderEngine

        engine = QoderEngine()
        with patch("shutil.which", return_value="/usr/bin/qoder"), \
             patch.dict(os.environ, {"DEVGODZILLA_ASSUME_AGENT_AUTH": "true"}, clear=False):
            result = engine.check_availability()
            assert result is True

    def test_register_qoder_engine(self):
        """Test Qoder engine registration function."""
        from devgodzilla.engines.qoder import register_qoder_engine

        engine = register_qoder_engine()
        assert engine.metadata.id == "qoder"


class TestQwenEngine:
    """Tests for Qwen Code CLI engine adapter."""

    def test_qwen_engine_metadata(self):
        """Test Qwen engine creation and metadata."""
        from devgodzilla.engines.qwen import QwenEngine

        engine = QwenEngine()
        assert engine.metadata.id == "qwen"
        assert engine.metadata.kind == EngineKind.CLI

    def test_qwen_engine_build_command(self, tmp_path: Path):
        """Test Qwen command building."""
        from devgodzilla.engines.qwen import QwenEngine

        engine = QwenEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Implement the feature",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "qwen"
        assert "--cwd" in cmd
        assert "--sandbox" in cmd
        assert "-" in cmd

    def test_qwen_engine_sandbox_mapping(self):
        """Test Qwen sandbox mode mapping."""
        from devgodzilla.engines.qwen import QwenEngine

        engine = QwenEngine()

        assert engine._sandbox_to_qwen(SandboxMode.FULL_ACCESS) == "full-access"
        assert engine._sandbox_to_qwen(SandboxMode.WORKSPACE_WRITE) == "workspace-write"
        assert engine._sandbox_to_qwen(SandboxMode.READ_ONLY) == "read-only"

    def test_qwen_engine_extra_options(self, tmp_path: Path):
        """Test Qwen engine with extra options."""
        from devgodzilla.engines.qwen import QwenEngine

        engine = QwenEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            extra={"auto_approve": True, "config": "custom.toml"},
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--auto-approve" in cmd
        assert "--config" in cmd

    def test_qwen_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.qwen import QwenEngine

        engine = QwenEngine()
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_qwen_engine_check_availability_with_api_key(self):
        """Test availability check with API key."""
        from devgodzilla.engines.qwen import QwenEngine

        engine = QwenEngine()
        with patch("shutil.which", return_value="/usr/bin/qwen"), \
             patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_register_qwen_engine(self):
        """Test Qwen engine registration function."""
        from devgodzilla.engines.qwen import register_qwen_engine

        engine = register_qwen_engine()
        assert engine.metadata.id == "qwen"


class TestAmazonQEngine:
    """Tests for Amazon Q CLI engine adapter."""

    def test_amazon_q_engine_metadata(self):
        """Test Amazon Q engine creation and metadata."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()
        assert engine.metadata.id == "amazon_q"
        assert engine.metadata.kind == EngineKind.CLI

    def test_amazon_q_engine_build_command(self, tmp_path: Path):
        """Test Amazon Q command building."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Generate code",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "q"  # Amazon Q uses 'q' command
        assert "--cwd" in cmd
        assert "--sandbox" in cmd
        assert "-" in cmd

    def test_amazon_q_engine_sandbox_mapping(self):
        """Test Amazon Q sandbox mode mapping."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()

        assert engine._sandbox_to_amazonq(SandboxMode.FULL_ACCESS) == "full-access"
        assert engine._sandbox_to_amazonq(SandboxMode.WORKSPACE_WRITE) == "workspace-write"
        assert engine._sandbox_to_amazonq(SandboxMode.READ_ONLY) == "read-only"

    def test_amazon_q_engine_extra_options(self, tmp_path: Path):
        """Test Amazon Q engine with extra options."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            extra={
                "no_confirm": True,
                "profile": "dev",
                "region": "us-west-2",
            },
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--no-confirm" in cmd
        assert "--profile" in cmd
        assert "--region" in cmd

    def test_amazon_q_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_amazon_q_engine_check_availability_with_aws(self):
        """Test availability check with AWS credentials."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()
        with patch("shutil.which", return_value="/usr/bin/q"), \
             patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_amazon_q_engine_check_availability_with_profile(self):
        """Test availability check with AWS profile."""
        from devgodzilla.engines.amazon_q import AmazonQEngine

        engine = AmazonQEngine()
        with patch("shutil.which", return_value="/usr/bin/q"), \
             patch.dict(os.environ, {"AWS_PROFILE": "dev"}):
            result = engine.check_availability()
            assert result is True

    def test_register_amazon_q_engine(self):
        """Test Amazon Q engine registration function."""
        from devgodzilla.engines.amazon_q import register_amazon_q_engine

        engine = register_amazon_q_engine()
        assert engine.metadata.id == "amazon_q"


class TestAuggieEngine:
    """Tests for Auggie (Augment) CLI engine adapter."""

    def test_auggie_engine_metadata(self):
        """Test Auggie engine creation and metadata."""
        from devgodzilla.engines.auggie import AuggieEngine

        engine = AuggieEngine()
        assert engine.metadata.id == "auggie"
        assert engine.metadata.kind == EngineKind.CLI

    def test_auggie_engine_build_command(self, tmp_path: Path):
        """Test Auggie command building."""
        from devgodzilla.engines.auggie import AuggieEngine

        engine = AuggieEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Implement feature",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "augment"
        assert "--cwd" in cmd
        assert "--sandbox" in cmd
        assert "-" in cmd

    def test_auggie_engine_sandbox_mapping(self):
        """Test Auggie sandbox mode mapping."""
        from devgodzilla.engines.auggie import AuggieEngine

        engine = AuggieEngine()

        assert engine._sandbox_to_auggie(SandboxMode.FULL_ACCESS) == "full-access"
        assert engine._sandbox_to_auggie(SandboxMode.WORKSPACE_WRITE) == "workspace-write"
        assert engine._sandbox_to_auggie(SandboxMode.READ_ONLY) == "read-only"

    def test_auggie_engine_extra_options(self, tmp_path: Path):
        """Test Auggie engine with extra options."""
        from devgodzilla.engines.auggie import AuggieEngine

        engine = AuggieEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            extra={
                "auto_approve": True,
                "rules_file": "custom_rules.md",
                "context": "additional context",
            },
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--auto-approve" in cmd
        assert "--rules" in cmd
        assert "--context" in cmd

    def test_auggie_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.auggie import AuggieEngine

        engine = AuggieEngine()
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_auggie_engine_check_availability_with_api_key(self):
        """Test availability check with API key."""
        from devgodzilla.engines.auggie import AuggieEngine

        engine = AuggieEngine()
        with patch("shutil.which", return_value="/usr/bin/augment"), \
             patch.dict(os.environ, {"AUGMENT_API_KEY": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_register_auggie_engine(self):
        """Test Auggie engine registration function."""
        from devgodzilla.engines.auggie import register_auggie_engine

        engine = register_auggie_engine()
        assert engine.metadata.id == "auggie"


class TestAllAdaptersIntegration:
    """Integration tests for all adapters."""

    def test_all_adapters_can_be_imported(self):
        """All adapter modules can be imported."""
        adapters = [
            "devgodzilla.engines.codex",
            "devgodzilla.engines.claude_code",
            "devgodzilla.engines.opencode",
            "devgodzilla.engines.cursor",
            "devgodzilla.engines.copilot",
            "devgodzilla.engines.qoder",
            "devgodzilla.engines.qwen",
            "devgodzilla.engines.amazon_q",
            "devgodzilla.engines.auggie",
            "devgodzilla.engines.codebuddy",
            "devgodzilla.engines.kilo",
            "devgodzilla.engines.roo",
        ]

        for adapter in adapters:
            __import__(adapter)

    def test_all_adapters_from_engines_module(self):
        """All adapters are accessible from engines module."""
        from devgodzilla import engines

        # Check that key adapters exist in the module
        assert hasattr(engines, "CodexEngine")
        assert hasattr(engines, "ClaudeCodeEngine")
        assert hasattr(engines, "OpenCodeEngine")
        assert hasattr(engines, "CursorEngine")
        assert hasattr(engines, "CopilotEngine")
        assert hasattr(engines, "QoderEngine")
        assert hasattr(engines, "QwenEngine")
        assert hasattr(engines, "AmazonQEngine")
        assert hasattr(engines, "AuggieEngine")
        assert hasattr(engines, "CodeBuddyEngine")
        assert hasattr(engines, "KiloEngine")
        assert hasattr(engines, "RooEngine")

    def test_all_adapters_have_required_metadata(self):
        """All adapters have required metadata fields."""
        from devgodzilla.engines.codex import CodexEngine
        from devgodzilla.engines.claude_code import ClaudeCodeEngine
        from devgodzilla.engines.opencode import OpenCodeEngine
        from devgodzilla.engines.cursor import CursorEngine
        from devgodzilla.engines.copilot import CopilotEngine
        from devgodzilla.engines.qoder import QoderEngine
        from devgodzilla.engines.qwen import QwenEngine
        from devgodzilla.engines.amazon_q import AmazonQEngine
        from devgodzilla.engines.auggie import AuggieEngine
        from devgodzilla.engines.codebuddy import CodeBuddyEngine
        from devgodzilla.engines.kilo import KiloEngine
        from devgodzilla.engines.roo import RooEngine

        engines = [
            CodexEngine(),
            ClaudeCodeEngine(),
            OpenCodeEngine(),
            CursorEngine(),
            CopilotEngine(),
            QoderEngine(),
            QwenEngine(),
            AmazonQEngine(),
            AuggieEngine(),
            CodeBuddyEngine(),
            KiloEngine(),
            RooEngine(),
        ]

        for engine in engines:
            assert engine.metadata.id is not None
            assert engine.metadata.display_name is not None
            assert engine.metadata.kind is not None
            assert isinstance(engine.metadata.capabilities, list)
            assert len(engine.metadata.capabilities) > 0

    def test_all_adapters_have_plan_execute_qa(self, tmp_path: Path):
        """All adapters implement plan, execute, and qa methods."""
        from devgodzilla.engines.qoder import QoderEngine
        from devgodzilla.engines.qwen import QwenEngine
        from devgodzilla.engines.amazon_q import AmazonQEngine
        from devgodzilla.engines.auggie import AuggieEngine
        from devgodzilla.engines.codebuddy import CodeBuddyEngine
        from devgodzilla.engines.kilo import KiloEngine
        from devgodzilla.engines.roo import RooEngine

        engines = [
            QoderEngine(),
            QwenEngine(),
            AmazonQEngine(),
            AuggieEngine(),
            CodeBuddyEngine(),
            KiloEngine(),
            RooEngine(),
        ]

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
        )

        for engine in engines:
            # All should have these methods
            assert hasattr(engine, "plan")
            assert hasattr(engine, "execute")
            assert hasattr(engine, "qa")
            assert callable(engine.plan)
            assert callable(engine.execute)
            assert callable(engine.qa)

    def test_all_cli_adapters_have_build_command(self, tmp_path: Path):
        """All CLI adapters implement _build_command."""
        from devgodzilla.engines.qoder import QoderEngine
        from devgodzilla.engines.qwen import QwenEngine
        from devgodzilla.engines.amazon_q import AmazonQEngine
        from devgodzilla.engines.auggie import AuggieEngine
        from devgodzilla.engines.codebuddy import CodeBuddyEngine
        from devgodzilla.engines.kilo import KiloEngine
        from devgodzilla.engines.roo import RooEngine

        engines = [
            QoderEngine(),
            QwenEngine(),
            AmazonQEngine(),
            AuggieEngine(),
            CodeBuddyEngine(),
            KiloEngine(),
            RooEngine(),
        ]

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
        )

        for engine in engines:
            cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
            assert isinstance(cmd, list)
            assert len(cmd) > 0
            assert isinstance(cmd[0], str)

    def test_all_registration_functions_work(self):
        """All registration functions can be called."""
        from devgodzilla.engines.qoder import register_qoder_engine, QoderEngine
        from devgodzilla.engines.qwen import register_qwen_engine, QwenEngine
        from devgodzilla.engines.amazon_q import register_amazon_q_engine, AmazonQEngine
        from devgodzilla.engines.auggie import register_auggie_engine, AuggieEngine
        from devgodzilla.engines.codebuddy import register_codebuddy_engine, CodeBuddyEngine
        from devgodzilla.engines.kilo import register_kilo_engine, KiloEngine
        from devgodzilla.engines.roo import register_roo_engine, RooEngine
        from devgodzilla.engines.registry import get_registry

        # Reset the registry to allow re-registration in tests
        from devgodzilla.engines.registry import _registry
        import devgodzilla.engines.registry as reg_module
        reg_module._registry = None

        engines = [
            register_qoder_engine(),
            register_qwen_engine(),
            register_amazon_q_engine(),
            register_auggie_engine(),
            register_codebuddy_engine(),
            register_kilo_engine(),
            register_roo_engine(),
        ]

        for engine in engines:
            assert engine is not None
            assert engine.metadata.id is not None


class TestCodeBuddyEngine:
    """Tests for CodeBuddy CLI engine adapter."""

    def test_codebuddy_engine_metadata(self):
        """Test CodeBuddy engine creation and metadata."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()
        assert engine.metadata.id == "codebuddy"
        assert engine.metadata.kind == EngineKind.CLI
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities

    def test_codebuddy_engine_build_command(self, tmp_path: Path):
        """Test CodeBuddy command building."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Create a new module",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "codebuddy"
        assert "--cwd" in cmd
        assert str(tmp_path) in cmd
        assert "--sandbox" in cmd
        assert "-" in cmd  # Read from stdin

    def test_codebuddy_engine_build_command_with_model(self, tmp_path: Path):
        """Test CodeBuddy command with custom model."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine(default_model="codebuddy-pro")

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            model="codebuddy-custom",
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "codebuddy-custom"

    def test_codebuddy_engine_sandbox_modes(self, tmp_path: Path):
        """Test CodeBuddy handles different sandbox modes."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
        )

        for sandbox in [SandboxMode.FULL_ACCESS, SandboxMode.READ_ONLY]:
            cmd = engine._build_command(req, sandbox)
            assert "--sandbox" in cmd

    def test_codebuddy_engine_extra_options(self, tmp_path: Path):
        """Test CodeBuddy engine with extra options."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            extra={"auto_approve": True, "config": "custom.toml", "context": "extra info"},
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--auto-approve" in cmd
        assert "--config" in cmd
        assert "--context" in cmd

    def test_codebuddy_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_codebuddy_engine_check_availability_with_auth(self):
        """Test availability check with auth environment variable."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()
        with patch("shutil.which", return_value="/usr/bin/codebuddy"), \
             patch.dict(os.environ, {"CODEBUDDY_API_KEY": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_codebuddy_engine_check_availability_assume_auth(self):
        """Test availability check with DEVGODZILLA_ASSUME_AGENT_AUTH."""
        from devgodzilla.engines.codebuddy import CodeBuddyEngine

        engine = CodeBuddyEngine()
        with patch("shutil.which", return_value="/usr/bin/codebuddy"), \
             patch.dict(os.environ, {"DEVGODZILLA_ASSUME_AGENT_AUTH": "true"}, clear=False):
            result = engine.check_availability()
            assert result is True

    def test_register_codebuddy_engine(self):
        """Test CodeBuddy engine registration function."""
        import devgodzilla.engines.registry as reg_module
        reg_module._registry = None

        from devgodzilla.engines.codebuddy import register_codebuddy_engine

        engine = register_codebuddy_engine()
        assert engine.metadata.id == "codebuddy"


class TestKiloEngine:
    """Tests for Kilo CLI engine adapter."""

    def test_kilo_engine_metadata(self):
        """Test Kilo engine creation and metadata."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()
        assert engine.metadata.id == "kilo"
        assert engine.metadata.kind == EngineKind.CLI
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities

    def test_kilo_engine_build_command(self, tmp_path: Path):
        """Test Kilo command building."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Implement the feature",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "kilo"
        assert "--cwd" in cmd
        assert "--sandbox" in cmd
        assert "-" in cmd

    def test_kilo_engine_sandbox_mapping(self):
        """Test Kilo sandbox mode mapping."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()

        assert engine._sandbox_to_kilo(SandboxMode.FULL_ACCESS) == "full-access"
        assert engine._sandbox_to_kilo(SandboxMode.WORKSPACE_WRITE) == "workspace-write"
        assert engine._sandbox_to_kilo(SandboxMode.READ_ONLY) == "read-only"

    def test_kilo_engine_extra_options(self, tmp_path: Path):
        """Test Kilo engine with extra options."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            extra={"auto_approve": True, "config": "custom.toml"},
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--auto-approve" in cmd
        assert "--config" in cmd

    def test_kilo_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_kilo_engine_check_availability_with_api_key(self):
        """Test availability check with API key."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()
        with patch("shutil.which", return_value="/usr/bin/kilo"), \
             patch.dict(os.environ, {"KILO_API_KEY": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_kilo_engine_check_availability_with_token(self):
        """Test availability check with token."""
        from devgodzilla.engines.kilo import KiloEngine

        engine = KiloEngine()
        with patch("shutil.which", return_value="/usr/bin/kilo"), \
             patch.dict(os.environ, {"KILO_TOKEN": "test-token"}):
            result = engine.check_availability()
            assert result is True

    def test_register_kilo_engine(self):
        """Test Kilo engine registration function."""
        import devgodzilla.engines.registry as reg_module
        reg_module._registry = None

        from devgodzilla.engines.kilo import register_kilo_engine

        engine = register_kilo_engine()
        assert engine.metadata.id == "kilo"


class TestRooEngine:
    """Tests for Roo CLI engine adapter."""

    def test_roo_engine_metadata(self):
        """Test Roo engine creation and metadata."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()
        assert engine.metadata.id == "roo"
        assert engine.metadata.kind == EngineKind.CLI
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities

    def test_roo_engine_build_command(self, tmp_path: Path):
        """Test Roo command building."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()
        # Force CLI name to "roo" so test doesn't depend on what's installed
        engine._cli_name = "roo"

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Generate code",
            working_dir=str(tmp_path),
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert cmd[0] == "roo"
        assert "--cwd" in cmd
        assert "--sandbox" in cmd
        assert "-" in cmd

    def test_roo_engine_sandbox_mapping(self):
        """Test Roo sandbox mode mapping."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()

        assert engine._sandbox_to_roo(SandboxMode.FULL_ACCESS) == "full-access"
        assert engine._sandbox_to_roo(SandboxMode.WORKSPACE_WRITE) == "workspace-write"
        assert engine._sandbox_to_roo(SandboxMode.READ_ONLY) == "read-only"

    def test_roo_engine_extra_options(self, tmp_path: Path):
        """Test Roo engine with extra options."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()
        engine._cli_name = "roo"

        req = EngineRequest(
            project_id=1,
            protocol_run_id=2,
            step_run_id=3,
            prompt_text="Test",
            working_dir=str(tmp_path),
            extra={
                "auto_approve": True,
                "config": "custom.toml",
                "context": "additional context",
            },
        )

        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)

        assert "--auto-approve" in cmd
        assert "--config" in cmd
        assert "--context" in cmd

    def test_roo_engine_check_availability_no_binary(self):
        """Test availability check when binary not found."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()
        with patch("shutil.which", return_value=None):
            result = engine.check_availability()
            assert result is False

    def test_roo_engine_check_availability_with_api_key(self):
        """Test availability check with API key."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()
        with patch("shutil.which", return_value="/usr/bin/roo"), \
             patch.dict(os.environ, {"ROO_API_KEY": "test-key"}):
            result = engine.check_availability()
            assert result is True

    def test_roo_engine_check_availability_with_roo_cli_fallback(self):
        """Test availability check falls back to roo-cli."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()

        def mock_which(name):
            if name == "roo":
                return None
            if name == "roo-cli":
                return "/usr/bin/roo-cli"
            return None

        with patch("shutil.which", side_effect=mock_which), \
             patch.dict(os.environ, {"ROO_TOKEN": "test-token"}):
            result = engine.check_availability()
            assert result is True

    def test_roo_engine_cli_name_prefers_roo(self):
        """Test that RooEngine prefers 'roo' over 'roo-cli'."""
        from devgodzilla.engines.roo import RooEngine

        engine = RooEngine()

        def mock_which(name):
            if name == "roo":
                return "/usr/bin/roo"
            if name == "roo-cli":
                return "/usr/bin/roo-cli"
            return None

        with patch("shutil.which", side_effect=mock_which):
            assert engine._get_command_name() == "roo"

    def test_register_roo_engine(self):
        """Test Roo engine registration function."""
        import devgodzilla.engines.registry as reg_module
        reg_module._registry = None

        from devgodzilla.engines.roo import register_roo_engine

        engine = register_roo_engine()
        assert engine.metadata.id == "roo"
