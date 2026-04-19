"""
Tests for Jules engine adapter (Google's AI coding agent, API-based).
"""

import os
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
from devgodzilla.engines.jules import JulesEngine, register_jules_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove agent-specific env vars so tests are deterministic."""
    for key in [
        "JULES_API_KEY", "GOOGLE_API_KEY",
        "DEVGODZILLA_JULES_BASE_URL", "DEVGODZILLA_JULES_MODEL",
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
# JulesEngine (APIEngine) tests
# ===================================================================

class TestJulesEngineMetadata:
    def test_metadata_id(self):
        engine = JulesEngine(api_key="test-key")
        assert engine.metadata.id == "jules"

    def test_metadata_kind_api(self):
        engine = JulesEngine(api_key="test-key")
        assert engine.metadata.kind == EngineKind.API

    def test_metadata_display_name(self):
        engine = JulesEngine(api_key="test-key")
        assert engine.metadata.display_name == "Google Jules"

    def test_metadata_capabilities(self):
        engine = JulesEngine(api_key="test-key")
        assert "plan" in engine.metadata.capabilities
        assert "execute" in engine.metadata.capabilities
        assert "qa" in engine.metadata.capabilities


class TestJulesEngineInit:
    def test_init_defaults(self, monkeypatch):
        engine = JulesEngine(api_key="k")
        assert engine._default_model == "jules-default"
        assert engine._base_url == "https://jules.google/api/v1"

    def test_init_custom_base_url(self):
        engine = JulesEngine(base_url="https://custom.api.com", api_key="k")
        assert engine._base_url == "https://custom.api.com"

    def test_init_env_model(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_JULES_MODEL", "jules-custom")
        engine = JulesEngine(api_key="k")
        assert engine._default_model == "jules-custom"

    def test_init_explicit_model_overrides_env(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_JULES_MODEL", "env-model")
        engine = JulesEngine(api_key="k", default_model="explicit-model")
        assert engine._default_model == "explicit-model"

    def test_init_env_base_url(self, monkeypatch):
        monkeypatch.setenv("DEVGODZILLA_JULES_BASE_URL", "https://env.api.com")
        engine = JulesEngine(api_key="k")
        assert engine._base_url == "https://env.api.com"

    def test_init_env_api_key_jules(self, monkeypatch):
        monkeypatch.setenv("JULES_API_KEY", "env-key")
        engine = JulesEngine()
        assert engine._api_key == "env-key"

    def test_init_env_api_key_google(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        engine = JulesEngine()
        assert engine._api_key == "google-key"

    def test_init_jules_key_preferred_over_google(self, monkeypatch):
        monkeypatch.setenv("JULES_API_KEY", "jules-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        engine = JulesEngine()
        assert engine._api_key == "jules-key"


class TestJulesEngineRequestBuilding:
    def test_build_request_config(self):
        engine = JulesEngine(base_url="https://jules.test", api_key="k")
        req = _make_request()
        config = engine._build_request_config(req, SandboxMode.WORKSPACE_WRITE)
        assert isinstance(config, APIRequestConfig)
        assert config.endpoint == "https://jules.test/execute"
        assert config.method == "POST"
        assert config.headers["X-Jules-Sandbox"] == "workspace-write"

    def test_build_request_body(self):
        engine = JulesEngine(api_key="k", default_model="jules-v2")
        req = _make_request()
        body = engine._build_request_body(req, SandboxMode.WORKSPACE_WRITE)
        assert body["prompt"] == "Write hello world"
        assert body["model"] == "test-model"
        assert body["sandbox"] == "workspace-write"
        assert body["working_dir"] == "/tmp/test-project"

    def test_build_request_body_uses_default_model(self):
        engine = JulesEngine(api_key="k", default_model="jules-v2")
        req = _make_request(model=None)
        body = engine._build_request_body(req, SandboxMode.FULL_ACCESS)
        assert body["model"] == "jules-v2"


class TestJulesEngineResponseParsing:
    def test_parse_success_response(self):
        engine = JulesEngine(api_key="k")
        req = _make_request()
        response = APIResponse(
            success=True,
            status_code=200,
            data={
                "output": "file created",
                "success": True,
                "model": "jules-v2",
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
        engine = JulesEngine(api_key="k")
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
        engine = JulesEngine(api_key="k")
        req = _make_request()
        response = APIResponse(success=True, status_code=200, data=None)
        result = engine._parse_response(response, req)
        assert result.success is False
        assert "Empty response" in result.error

    def test_parse_response_with_error_field(self):
        engine = JulesEngine(api_key="k")
        req = _make_request()
        response = APIResponse(
            success=True,
            status_code=200,
            data={"output": "partial", "success": True, "error": "something went wrong"},
        )
        result = engine._parse_response(response, req)
        assert result.success is False
        assert result.error == "something went wrong"


class TestJulesEngineAvailability:
    def test_not_available_without_api_key(self):
        engine = JulesEngine()
        assert engine.check_availability() is False

    def test_not_available_with_key_but_no_health(self, monkeypatch):
        engine = JulesEngine(base_url="https://nonexistent.test", api_key="k")
        assert engine.check_availability() is False

    def test_available_with_mock_health(self, monkeypatch):
        engine = JulesEngine(base_url="https://api.test", api_key="k")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert engine.check_availability() is True


class TestJulesEngineExecution:
    def test_plan_uses_full_access(self):
        engine = JulesEngine(base_url="https://api.test", api_key="k")
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
        engine = JulesEngine(base_url="https://api.test", api_key="k")
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
        engine = JulesEngine(base_url="https://api.test", api_key="k")
        req = _make_request()
        with patch.object(
            engine,
            "_make_request",
            return_value=APIResponse(success=True, status_code=200, data={"output": "ok", "success": True}),
        ):
            result = engine.qa(req)
            assert result.success is True
            assert result.metadata["sandbox"] == "read-only"


class TestJulesEngineRegistration:
    def test_register_jules_engine(self, _reset_registry):
        engine = register_jules_engine()
        assert engine.metadata.id == "jules"
        registry = get_registry()
        assert registry.has("jules")

    def test_register_jules_engine_default(self, _reset_registry):
        engine = register_jules_engine(default=True)
        registry = get_registry()
        assert registry.get_default().metadata.id == "jules"
