"""
Tests for Amp, SHAI, and Bob engine adapters.
"""

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from devgodzilla.engines.interface import (
    EngineKind,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.engines.api_engine import APIRequestConfig, APIResponse
from devgodzilla.engines.registry import EngineRegistry, get_registry, _reset_registry_for_tests
from devgodzilla.engines.amp import AmpEngine, register_amp_engine
from devgodzilla.engines.shai import SHAIEngine, register_shai_engine
from devgodzilla.engines.bob import BobEngine, register_bob_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove agent-specific env vars so tests are deterministic."""
    for key in [
        "AMP_API_KEY", "DEVGODZILLA_AMP_BASE_URL", "DEVGODZILLA_AMP_MODEL",
        "SHAI_API_KEY", "SHAI_TOKEN", "DEVGODZILLA_SHAI_MODEL",
        "BOB_API_KEY", "BOB_TOKEN", "DEVGODZILLA_BOB_MODEL",
        "DEVGODZILLA_ASSUME_AGENT_AUTH",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def _reset_registry():
    """Reset global registry before and after each test."""
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()


def _make_request(**overrides) -> EngineRequest:
    defaults = dict(
        project_id=1,
        protocol_run_id=2,
        step_run_id=3,
        prompt_text="Write hello world",
        working_dir="/tmp/test-project",
        model="test-model",
        sandbox=SandboxMode.WORKSPACE_WRITE,
        timeout=30,
    )
    defaults.update(overrides)
    return EngineRequest(**defaults)


# ===================================================================
# AmpEngine (APIEngine) tests
# ===================================================================

class TestAmpEngineMetadata:
    def test_metadata_id(self):
        engine = AmpEngine(api_key="test-key")
        assert engine.metadata.id == "amp"

    def test_metadata_kind_api(self):
        engine = AmpEngine(api_key="test-key")
        assert engine.metadata.kind == EngineKind.API

    def test_metadata_display_name(self):
        engine = AmpEngine(api_key="test-key")
        assert engine.metadata.display_name == "Amp AI Agent"

    def test_metadata_capabilities(self):
        engine = AmpEngine(api_key="test-key")
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities
        assert "qa" in engine.metadata.capabilities


class TestAmpEngineInit:
    def test_init_defaults(self, monkeypatch):
        engine = AmpEngine(api_key="k")
        assert engine._default_model == "amp-default"
        assert engine._base_url == "https://api.ampcode.com/v1"

    def test_init_custom_base_url(self):
        engine = AmpEngine(base_url="https://custom.api.com", api_key="k")
        assert engine._base_url == "https://custom.api.com"

    def test_init_env_model(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_AMP_MODEL", "amp-custom")
        engine = AmpEngine(api_key="k")
        assert engine._default_model == "amp-custom"

    def test_init_explicit_model_overrides_env(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_AMP_MODEL", "env-model")
        engine = AmpEngine(api_key="k", default_model="explicit-model")
        assert engine._default_model == "explicit-model"

    def test_init_env_base_url(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_AMP_BASE_URL", "https://env.api.com")
        engine = AmpEngine(api_key="k")
        assert engine._base_url == "https://env.api.com"

    def test_init_env_api_key(self, monkeypatch):
        monkeypatch.setenv("AMP_API_KEY", "env-key")
        engine = AmpEngine()
        assert engine._api_key == "env-key"


class TestAmpEngineRequestBuilding:
    def test_build_request_config(self):
        engine = AmpEngine(base_url="https://api.amp.test", api_key="k")
        req = _make_request()
        config = engine._build_request_config(req, SandboxMode.WORKSPACE_WRITE)
        assert isinstance(config, APIRequestConfig)
        assert config.endpoint == "https://api.amp.test/execute"
        assert config.method == "POST"
        assert config.headers["X-Amp-Sandbox"] == "workspace-write"

    def test_build_request_body(self):
        engine = AmpEngine(api_key="k", default_model="amp-v2")
        req = _make_request()
        body = engine._build_request_body(req, SandboxMode.WORKSPACE_WRITE)
        assert body["prompt"] == "Write hello world"
        assert body["model"] == "test-model"
        assert body["sandbox"] == "workspace-write"
        assert body["working_dir"] == "/tmp/test-project"

    def test_build_request_body_uses_default_model(self):
        engine = AmpEngine(api_key="k", default_model="amp-v2")
        req = _make_request(model=None)
        body = engine._build_request_body(req, SandboxMode.FULL_ACCESS)
        assert body["model"] == "amp-v2"


class TestAmpEngineResponseParsing:
    def test_parse_success_response(self):
        engine = AmpEngine(api_key="k")
        req = _make_request()
        response = APIResponse(
            success=True,
            status_code=200,
            data={
                "output": "file created",
                "success": True,
                "model": "amp-v2",
                "usage": {
                    "total_tokens": 150,
                    "prompt_tokens": 50,
                    "completion_tokens": 100,
                    "cost_cents": 5,
                },
            },
        )
        result = engine._parse_response(response, req)
        assert result.success is True
        assert result.stdout == "file created"
        assert result.tokens_used == 150
        assert result.cost_cents == 5

    def test_parse_failure_response(self):
        engine = AmpEngine(api_key="k")
        req = _make_request()
        response = APIResponse(
            success=False,
            status_code=500,
            error="Internal server error",
        )
        result = engine._parse_response(response, req)
        assert result.success is False
        assert "Internal server error" in result.error

    def test_parse_empty_response(self):
        engine = AmpEngine(api_key="k")
        req = _make_request()
        response = APIResponse(success=True, status_code=200, data=None)
        result = engine._parse_response(response, req)
        assert result.success is False
        assert "Empty response" in result.error

    def test_parse_response_with_error_field(self):
        engine = AmpEngine(api_key="k")
        req = _make_request()
        response = APIResponse(
            success=True,
            status_code=200,
            data={"output": "partial", "success": True, "error": "something went wrong"},
        )
        result = engine._parse_response(response, req)
        assert result.success is False
        assert result.error == "something went wrong"


class TestAmpEngineAvailability:
    def test_not_available_without_api_key(self):
        engine = AmpEngine()
        assert engine.check_availability() is False

    def test_not_available_with_key_but_no_health(self, monkeypatch):
        engine = AmpEngine(base_url="https://nonexistent.test", api_key="k")
        # Health check will fail (no server), but at least api_key check passes
        # Actually super().check_availability() hits /health which will fail
        assert engine.check_availability() is False

    def test_available_with_mock_health(self, monkeypatch):
        engine = AmpEngine(base_url="https://api.test", api_key="k")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert engine.check_availability() is True


class TestAmpEngineExecution:
    def test_plan_uses_full_access(self):
        engine = AmpEngine(base_url="https://api.test", api_key="k")
        req = _make_request()
        with patch.object(
            engine,
            "_make_request",
            return_value=APIResponse(success=True, status_code=200, data={"output": "ok", "success": True}),
        ):
            result = engine.plan(req)
            assert result.success is True
            assert result.metadata["sandbox"] == "full-access"

    def test_execute_uses_workspace_write(self):
        engine = AmpEngine(base_url="https://api.test", api_key="k")
        req = _make_request()
        with patch.object(
            engine,
            "_make_request",
            return_value=APIResponse(success=True, status_code=200, data={"output": "ok", "success": True}),
        ):
            result = engine.execute(req)
            assert result.success is True
            assert result.metadata["sandbox"] == "workspace-write"

    def test_qa_uses_read_only(self):
        engine = AmpEngine(base_url="https://api.test", api_key="k")
        req = _make_request()
        with patch.object(
            engine,
            "_make_request",
            return_value=APIResponse(success=True, status_code=200, data={"output": "ok", "success": True}),
        ):
            result = engine.qa(req)
            assert result.success is True
            assert result.metadata["sandbox"] == "read-only"


# ===================================================================
# SHAIEngine (CLIEngine) tests
# ===================================================================

class TestSHAIEngineMetadata:
    def test_metadata_id(self):
        engine = SHAIEngine()
        assert engine.metadata.id == "shai"

    def test_metadata_kind_cli(self):
        engine = SHAIEngine()
        assert engine.metadata.kind == EngineKind.CLI

    def test_metadata_display_name(self):
        engine = SHAIEngine()
        assert engine.metadata.display_name == "SHAI AI Assistant"

    def test_metadata_capabilities(self):
        engine = SHAIEngine()
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities
        assert "qa" in engine.metadata.capabilities


class TestSHAIEngineInit:
    def test_init_defaults(self):
        engine = SHAIEngine()
        assert engine._default_model == "shai-default"

    def test_init_custom_model(self):
        engine = SHAIEngine(default_model="shai-v3")
        assert engine._default_model == "shai-v3"

    def test_init_env_model(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_SHAI_MODEL", "shai-env")
        engine = SHAIEngine()
        assert engine._default_model == "shai-env"


class TestSHAIEngineCommand:
    def test_build_command_basic(self):
        engine = SHAIEngine()
        req = _make_request(working_dir="/tmp/project")
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert cmd[0] == "shai"
        assert "--cwd" in cmd
        assert "/tmp/project" in cmd
        assert "--sandbox" in cmd
        assert "workspace-write" in cmd
        assert "--model" in cmd
        assert "test-model" in cmd
        assert cmd[-1] == "-"

    def test_build_command_plan_mode(self):
        engine = SHAIEngine()
        req = _make_request()
        cmd = engine._build_command(req, SandboxMode.FULL_ACCESS)
        assert "full-access" in cmd

    def test_build_command_qa_mode(self):
        engine = SHAIEngine()
        req = _make_request()
        cmd = engine._build_command(req, SandboxMode.READ_ONLY)
        assert "read-only" in cmd

    def test_build_command_auto_approve(self):
        engine = SHAIEngine()
        req = _make_request(extra={"auto_approve": True})
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert "--auto-approve" in cmd

    def test_build_command_verbose(self):
        engine = SHAIEngine()
        req = _make_request(extra={"verbose": True})
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert "--verbose" in cmd

    def test_build_command_no_model_uses_default(self):
        engine = SHAIEngine()
        req = _make_request(model=None)
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        # When no model in request, _get_model falls back to default
        assert "--model" in cmd
        assert "shai-default" in cmd

    def test_command_name_is_shai(self):
        engine = SHAIEngine()
        assert engine._get_command_name() == "shai"


class TestSHAIEngineExecution:
    def test_execute_calls_run_cli(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_cli(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["cwd"] = kwargs.get("cwd")
            captured["input_text"] = kwargs.get("input_text")
            return EngineResult(
                success=True,
                stdout="done",
                stderr="",
                exit_code=0,
                duration_seconds=0.1,
                metadata={"cmd": cmd[0]},
            )

        monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli)
        engine = SHAIEngine()
        req = _make_request(working_dir=str(tmp_path))
        result = engine.execute(req)
        assert result.success is True
        assert captured["cmd"][0] == "shai"
        assert captured["input_text"] == "Write hello world"

    def test_plan_calls_run_cli(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_cli(cmd, **kwargs):
            captured["sandbox_in_cmd"] = "full-access" in " ".join(cmd)
            return EngineResult(success=True, stdout="", stderr="", metadata={"cmd": cmd[0]})

        monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli)
        engine = SHAIEngine()
        req = _make_request(working_dir=str(tmp_path))
        result = engine.plan(req)
        assert captured["sandbox_in_cmd"] is True

    def test_qa_calls_run_cli(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_cli(cmd, **kwargs):
            captured["sandbox_in_cmd"] = "read-only" in " ".join(cmd)
            return EngineResult(success=True, stdout="", stderr="", metadata={"cmd": cmd[0]})

        monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli)
        engine = SHAIEngine()
        req = _make_request(working_dir=str(tmp_path))
        result = engine.qa(req)
        assert captured["sandbox_in_cmd"] is True


class TestSHAIEngineAvailability:
    def test_not_available_without_binary(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        engine = SHAIEngine()
        assert engine.check_availability() is False

    def test_available_with_assume_auth(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_ASSUME_AGENT_AUTH", "1")
        engine = SHAIEngine()
        # super().check_availability() uses shutil.which; patch it
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/shai")
        assert engine.check_availability() is True

    def test_available_with_api_key(self, monkeypatch):
        monkeypatch.setenv("SHAI_API_KEY", "test-key")
        engine = SHAIEngine()
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/shai")
        assert engine.check_availability() is True

    def test_available_with_token(self, monkeypatch):
        monkeypatch.setenv("SHAI_TOKEN", "test-token")
        engine = SHAIEngine()
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/shai")
        assert engine.check_availability() is True


# ===================================================================
# BobEngine (CLIEngine) tests
# ===================================================================

class TestBobEngineMetadata:
    def test_metadata_id(self):
        engine = BobEngine()
        assert engine.metadata.id == "bob"

    def test_metadata_kind_cli(self):
        engine = BobEngine()
        assert engine.metadata.kind == EngineKind.CLI

    def test_metadata_display_name(self):
        engine = BobEngine()
        assert engine.metadata.display_name == "Bob AI Coding Bot"

    def test_metadata_capabilities(self):
        engine = BobEngine()
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities
        assert "qa" in engine.metadata.capabilities


class TestBobEngineInit:
    def test_init_defaults(self):
        engine = BobEngine()
        assert engine._default_model == "bob-default"

    def test_init_custom_model(self):
        engine = BobEngine(default_model="bob-v2")
        assert engine._default_model == "bob-v2"

    def test_init_env_model(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_BOB_MODEL", "bob-env")
        engine = BobEngine()
        assert engine._default_model == "bob-env"


class TestBobEngineCommand:
    def test_build_command_basic(self):
        engine = BobEngine()
        req = _make_request(working_dir="/tmp/project")
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert cmd[0] == "bob"
        assert "--cwd" in cmd
        assert "/tmp/project" in cmd
        assert "--sandbox" in cmd
        assert "workspace-write" in cmd
        assert "--model" in cmd
        assert "test-model" in cmd
        assert cmd[-1] == "-"

    def test_build_command_plan_mode(self):
        engine = BobEngine()
        req = _make_request()
        cmd = engine._build_command(req, SandboxMode.FULL_ACCESS)
        assert "full-access" in cmd

    def test_build_command_qa_mode(self):
        engine = BobEngine()
        req = _make_request()
        cmd = engine._build_command(req, SandboxMode.READ_ONLY)
        assert "read-only" in cmd

    def test_build_command_auto_approve(self):
        engine = BobEngine()
        req = _make_request(extra={"auto_approve": True})
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert "--auto-approve" in cmd

    def test_build_command_verbose(self):
        engine = BobEngine()
        req = _make_request(extra={"verbose": True})
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert "--verbose" in cmd

    def test_build_command_rules_file(self):
        engine = BobEngine()
        req = _make_request(extra={"rules_file": "/path/to/rules"})
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        assert "--rules" in cmd
        assert "/path/to/rules" in cmd

    def test_build_command_no_model_uses_default(self):
        engine = BobEngine()
        req = _make_request(model=None)
        cmd = engine._build_command(req, SandboxMode.WORKSPACE_WRITE)
        # When no model in request, _get_model falls back to default
        assert "--model" in cmd
        assert "bob-default" in cmd

    def test_command_name_is_bob(self):
        engine = BobEngine()
        assert engine._get_command_name() == "bob"


class TestBobEngineExecution:
    def test_execute_calls_run_cli(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_cli(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["cwd"] = kwargs.get("cwd")
            captured["input_text"] = kwargs.get("input_text")
            return EngineResult(
                success=True,
                stdout="done",
                stderr="",
                exit_code=0,
                duration_seconds=0.1,
                metadata={"cmd": cmd[0]},
            )

        monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli)
        engine = BobEngine()
        req = _make_request(working_dir=str(tmp_path))
        result = engine.execute(req)
        assert result.success is True
        assert captured["cmd"][0] == "bob"
        assert captured["input_text"] == "Write hello world"

    def test_plan_calls_run_cli(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_cli(cmd, **kwargs):
            captured["sandbox_in_cmd"] = "full-access" in " ".join(cmd)
            return EngineResult(success=True, stdout="", stderr="", metadata={"cmd": cmd[0]})

        monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli)
        engine = BobEngine()
        req = _make_request(working_dir=str(tmp_path))
        result = engine.plan(req)
        assert captured["sandbox_in_cmd"] is True

    def test_qa_calls_run_cli(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run_cli(cmd, **kwargs):
            captured["sandbox_in_cmd"] = "read-only" in " ".join(cmd)
            return EngineResult(success=True, stdout="", stderr="", metadata={"cmd": cmd[0]})

        monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli)
        engine = BobEngine()
        req = _make_request(working_dir=str(tmp_path))
        result = engine.qa(req)
        assert captured["sandbox_in_cmd"] is True


class TestBobEngineAvailability:
    def test_not_available_without_binary(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        engine = BobEngine()
        assert engine.check_availability() is False

    def test_available_with_assume_auth(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_ASSUME_AGENT_AUTH", "1")
        engine = BobEngine()
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/bob")
        assert engine.check_availability() is True

    def test_available_with_api_key(self, monkeypatch):
        monkeypatch.setenv("BOB_API_KEY", "test-key")
        engine = BobEngine()
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/bob")
        assert engine.check_availability() is True

    def test_available_with_token(self, monkeypatch):
        monkeypatch.setenv("BOB_TOKEN", "test-token")
        engine = BobEngine()
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/bob")
        assert engine.check_availability() is True


# ===================================================================
# Registry integration tests
# ===================================================================

class TestRegistryIntegration:
    def test_register_amp_engine(self, _reset_registry):
        engine = register_amp_engine()
        registry = get_registry()
        assert registry.has("amp")
        assert registry.get("amp") is engine

    def test_register_shai_engine(self, _reset_registry):
        engine = register_shai_engine()
        registry = get_registry()
        assert registry.has("shai")
        assert registry.get("shai") is engine

    def test_register_bob_engine(self, _reset_registry):
        engine = register_bob_engine()
        registry = get_registry()
        assert registry.has("bob")
        assert registry.get("bob") is engine

    def test_register_all_three(self, _reset_registry):
        register_amp_engine()
        register_shai_engine()
        register_bob_engine()
        registry = get_registry()
        assert registry.has("amp")
        assert registry.has("shai")
        assert registry.has("bob")

    def test_list_by_kind_api_finds_amp(self, _reset_registry):
        register_amp_engine()
        registry = get_registry()
        api_engines = registry.list_by_kind(EngineKind.API)
        ids = [e.metadata.id for e in api_engines]
        assert "amp" in ids

    def test_list_by_kind_cli_finds_shai_and_bob(self, _reset_registry):
        register_shai_engine()
        register_bob_engine()
        registry = get_registry()
        cli_engines = registry.list_by_kind(EngineKind.CLI)
        ids = [e.metadata.id for e in cli_engines]
        assert "shai" in ids
        assert "bob" in ids

    def test_register_amp_as_default(self, _reset_registry):
        register_amp_engine(default=True)
        registry = get_registry()
        assert registry.get_default().metadata.id == "amp"

    def test_register_prevents_duplicate(self, _reset_registry):
        register_amp_engine()
        registry = get_registry()
        with pytest.raises(ValueError, match="already registered"):
            registry.register(AmpEngine(api_key="k"))

    def test_register_replace_allows_duplicate(self, _reset_registry):
        register_amp_engine()
        new_engine = AmpEngine(api_key="new-key", default_model="amp-v3")
        registry = get_registry()
        registry.register(new_engine, replace=True)
        assert registry.get("amp").metadata.default_model == "amp-v3"
