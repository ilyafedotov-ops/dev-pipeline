"""
Integration tests for agent management API endpoints.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    TestClient = None  # type: ignore

from devgodzilla.api.app import app
from devgodzilla.db.database import SQLiteDatabase


OPENCODE_VERBOSE_MODELS = """
openai/gpt-5-nano
{
  "id": "gpt-5-nano",
  "providerID": "openai",
  "capabilities": {
    "reasoning": true
  },
  "variants": {
    "minimal": {"reasoningEffort": "minimal"},
    "low": {"reasoningEffort": "low"},
    "medium": {"reasoningEffort": "medium"},
    "high": {"reasoningEffort": "high"}
  }
}
openai/gpt-4.1
{
  "id": "gpt-4.1",
  "providerID": "openai",
  "capabilities": {
    "reasoning": false
  },
  "variants": {}
}
anthropic/claude-sonnet-4
{
  "id": "claude-sonnet-4",
  "providerID": "anthropic",
  "capabilities": {
    "reasoning": false
  },
  "variants": {}
}
""".strip()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_agents_api_defaults_prompts_overrides(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  alpha:
    name: Alpha Agent
    kind: api
    endpoint: https://example.com/api
    capabilities: [code_gen]
    enabled: true
  beta:
    name: Beta Agent
    kind: api
    endpoint: https://example.com/qa
    capabilities: [qa]
    enabled: false
defaults:
  exec: alpha
  qa: beta
  prompts:
    exec: exec-template
    qa: qa-template
prompts:
  exec-template:
    name: Exec Template
    path: prompts/exec.prompt.md
    kind: exec
  qa-template:
    name: QA Template
    path: prompts/qa.prompt.md
    kind: qa
projects:
  "1":
    inherit: true
    agents:
      alpha:
        enabled: false
    defaults:
      exec: beta
    prompts:
      exec-template:
        name: Project Exec Template
        path: prompts/exec.project.prompt.md
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="Agent Test",
            git_url="https://example.com/repo.git",
            base_branch="main",
        )
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="agents-protocol",
            status="running",
            base_branch="main",
        )
        db.create_step_run(
            protocol_run_id=run.id,
            step_index=0,
            step_name="step-00",
            step_type="execute",
            status="running",
            assigned_agent="alpha",
        )
        db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01",
            step_type="execute",
            status="completed",
            assigned_agent="alpha",
        )

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents")
                assert resp.status_code == 200
                agents = {a["id"]: a for a in resp.json()}
                assert agents["alpha"]["enabled"] is True
                assert agents["beta"]["enabled"] is False
                assert agents["alpha"]["status"] == "configured"
                assert agents["beta"]["status"] == "disabled"

                resp = client.get(f"/agents?project_id={project.id}")
                assert resp.status_code == 200
                project_agents = {a["id"]: a for a in resp.json()}
                assert project_agents["alpha"]["enabled"] is False
                assert project_agents["beta"]["enabled"] is False
                assert project_agents["alpha"]["status"] == "disabled"
                assert project_agents["beta"]["status"] == "disabled"

                resp = client.get("/agents/defaults")
                assert resp.status_code == 200
                defaults = resp.json()
                assert defaults["exec"] == "alpha"
                assert defaults["qa"] == "beta"

                resp = client.get(f"/agents/defaults?project_id={project.id}")
                assert resp.status_code == 200
                project_defaults = resp.json()
                assert project_defaults["exec"] == "beta"

                resp = client.put(
                    f"/agents/defaults?project_id={project.id}",
                    json={"exec": "alpha"},
                )
                assert resp.status_code == 200
                assert resp.json()["exec"] == "alpha"

                resp = client.get(f"/agents/prompts?project_id={project.id}")
                assert resp.status_code == 200
                prompts = {p["id"]: p for p in resp.json()}
                assert prompts["exec-template"]["source"] == "project"
                assert prompts["qa-template"]["source"] == "global"

                resp = client.get(f"/agents/projects/{project.id}")
                assert resp.status_code == 200
                overrides = resp.json()
                assert overrides["inherit"] is True

                resp = client.put(
                    f"/agents/projects/{project.id}",
                    json={"inherit": False},
                )
                assert resp.status_code == 200
                assert resp.json()["inherit"] is False

                resp = client.get(f"/agents/metrics?project_id={project.id}")
                assert resp.status_code == 200
                metrics = {m["agent_id"]: m for m in resp.json()}
                assert metrics["alpha"]["active_steps"] == 1
                assert metrics["alpha"]["completed_steps"] == 1
                assert metrics["alpha"]["total_steps"] == 2
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_agents_api_test_setup_endpoint(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  alpha:
    name: Alpha Agent
    kind: cli
    command: python3
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: alpha
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post("/agents/alpha/test", json={"overrides": {}})
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["agent_id"] == "alpha"
                assert "checks" in payload
                assert any(c["name"] == "version" for c in payload["checks"])

                resp = client.post("/agents/does-not-exist/test", json={"overrides": {}})
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_codex_setup_accepts_login_without_openai_api_key(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-5.4
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEVGODZILLA_ASSUME_AGENT_AUTH", raising=False)
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            """
{"models":[{"slug":"gpt-5.4"},{"slug":"gpt-5.3-codex"}]}
""".strip()
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["codex", "--version"]:
                return Result(0, stdout="codex 1.2.3\n")
            if args == ["codex", "login", "status"]:
                return Result(0, stdout="Logged in as subscription user\n")
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post("/agents/codex/test", json={"overrides": {}})
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["ok"] is True
                checks = {c["name"]: c for c in payload["checks"]}
                assert "auth" in checks
                assert checks["auth"]["ok"] is True
                assert checks["model"]["ok"] is True
                assert "openai_api_key" not in checks
                assert checks["auth"]["details"]["logged_in"] is True
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_agent_models_endpoint_returns_codex_cached_list(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-4.1
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            """
{"models":[
  {"slug":"gpt-5.4","default_reasoning_level":"medium","supported_reasoning_levels":[{"effort":"low","description":"Low"},{"effort":"medium","description":"Medium"},{"effort":"high","description":"High"}]},
  {"slug":"gpt-5.4-mini","default_reasoning_level":"medium","supported_reasoning_levels":[{"effort":"low","description":"Low"},{"effort":"medium","description":"Medium"},{"effort":"high","description":"High"}]},
  {"slug":"gpt-5.3-codex","default_reasoning_level":"medium","supported_reasoning_levels":[{"effort":"low","description":"Low"},{"effort":"medium","description":"Medium"},{"effort":"high","description":"High"}]}
]}
""".strip()
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents/codex/models")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["agent_id"] == "codex"
                assert payload["source"] == "cache"
                assert payload["models"] == ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]
                assert payload["warning"] is None
                assert payload["model_details"]["gpt-5.4"]["default_reasoning_effort"] == "medium"
                assert payload["model_details"]["gpt-5.4"]["supported_reasoning_efforts"][0]["effort"] == "low"
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_codex_models_endpoint_returns_empty_list_when_cache_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-5.4
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents/codex/models")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["agent_id"] == "codex"
                assert payload["source"] == "cache"
                assert payload["models"] == []
                assert "No local Codex model cache found" in (payload["warning"] or "")
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_codex_models_refresh_endpoint_returns_cached_list(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-5.4
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            """
{"models":[{"slug":"gpt-5.4"},{"slug":"gpt-5.3-codex"}]}
""".strip()
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post("/agents/codex/models/refresh")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["agent_id"] == "codex"
                assert payload["source"] == "cache"
                assert payload["models"] == ["gpt-5.4", "gpt-5.3-codex"]
                assert payload["warning"] is None
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_codex_setup_fails_for_non_codex_model(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-5.4
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEVGODZILLA_ASSUME_AGENT_AUTH", raising=False)
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            """
{"models":[{"slug":"gpt-5.4"},{"slug":"gpt-5.3-codex"}]}
""".strip()
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["codex", "--version"]:
                return Result(0, stdout="codex 1.2.3\n")
            if args == ["codex", "login", "status"]:
                return Result(0, stdout="Logged in as subscription user\n")
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    "/agents/codex/test",
                    json={"overrides": {"default_model": "claude-sonnet-4-20250514"}},
                )
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["ok"] is False
                checks = {c["name"]: c for c in payload["checks"]}
                assert checks["auth"]["ok"] is True
                assert checks["model"]["ok"] is False
                assert "claude-sonnet-4-20250514" in (checks["model"]["error"] or "")
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_update_agent_config_rejects_invalid_codex_model(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-5.4
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            """
{"models":[{"slug":"gpt-5.4"},{"slug":"gpt-5.3-codex"}]}
""".strip()
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.put("/agents/codex/config", json={"default_model": "claude-sonnet-4-20250514"})
                assert resp.status_code == 400
                assert "Invalid model for codex" in resp.json()["detail"]

                resp = client.get("/agents/codex")
                assert resp.status_code == 200
                assert resp.json()["default_model"] == "gpt-5.4"
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_update_agent_config_rejects_invalid_codex_reasoning_effort(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  codex:
    name: OpenAI Codex
    kind: cli
    command: codex
    default_model: gpt-5.4
    reasoning_effort: medium
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: codex
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            """
{"models":[{"slug":"gpt-5.4","default_reasoning_level":"medium","supported_reasoning_levels":[{"effort":"low","description":"Low"},{"effort":"medium","description":"Medium"},{"effort":"high","description":"High"}]}]}
""".strip()
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.put("/agents/codex/config", json={"reasoning_effort": "xhigh"})
                assert resp.status_code == 400
                assert "Invalid reasoning_effort" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_agent_models_endpoint_returns_opencode_cli_models(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: openai/gpt-5-nano
    reasoning_effort: medium
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["opencode", "models", "--verbose"]:
                return Result(0, stdout=OPENCODE_VERBOSE_MODELS)
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents/opencode/models")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["agent_id"] == "opencode"
                assert payload["source"] == "cli"
                assert payload["models"] == [
                    "openai/gpt-5-nano",
                    "openai/gpt-4.1",
                    "anthropic/claude-sonnet-4",
                ]
                assert payload["model_details"]["openai/gpt-5-nano"]["default_reasoning_effort"] == "medium"
                assert payload["model_details"]["openai/gpt-5-nano"]["supported_reasoning_efforts"][0]["effort"] == "minimal"
                assert payload["model_details"]["openai/gpt-4.1"]["supported_reasoning_efforts"] == []
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_opencode_models_refresh_endpoint_uses_cli_refresh(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: openai/gpt-5-nano
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        calls: list[list[str]] = []

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            calls.append(args)
            if args == ["opencode", "models", "--verbose", "--refresh"]:
                return Result(0, stdout=OPENCODE_VERBOSE_MODELS)
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post("/agents/opencode/models/refresh")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["source"] == "cli"
                assert payload["models"][0] == "openai/gpt-5-nano"
                assert calls == [["opencode", "models", "--verbose", "--refresh"]]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_opencode_models_refresh_falls_back_to_current_cli_list_on_refresh_timeout(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: openai/gpt-5-nano
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        calls: list[list[str]] = []

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            calls.append(args)
            if args == ["opencode", "models", "--verbose", "--refresh"]:
                raise subprocess.TimeoutExpired(args, timeout)
            if args == ["opencode", "models", "--verbose"]:
                return Result(0, stdout=OPENCODE_VERBOSE_MODELS)
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post("/agents/opencode/models/refresh")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["source"] == "cli"
                assert payload["models"] == [
                    "openai/gpt-5-nano",
                    "openai/gpt-4.1",
                    "anthropic/claude-sonnet-4",
                ]
                assert "Showing the current CLI-discovered model list instead." in payload["warning"]
                assert calls == [
                    ["opencode", "models", "--verbose", "--refresh"],
                    ["opencode", "models", "--verbose"],
                ]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_gemini_models_endpoint_returns_bundle_models(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  gemini-cli:
    name: Gemini CLI
    kind: cli
    command: gemini
    default_model: gemini-2.5-pro
    capabilities: [code_gen, reasoning]
    enabled: true
defaults:
  exec: gemini-cli
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        monkeypatch.setattr(
            agent_config_module.AgentConfigService,
            "_discover_gemini_models",
            lambda self, timeout=20: (
                ["auto", "flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
                "bundle",
                "Using Gemini CLI bundle-discovered model aliases; account access may vary by auth context.",
                {},
            ),
        )

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents/gemini-cli/models")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["agent_id"] == "gemini-cli"
                assert payload["source"] == "bundle"
                assert payload["models"] == ["auto", "flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_gemini_setup_rejects_invalid_model_and_reasoning(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  gemini-cli:
    name: Gemini CLI
    kind: cli
    command: gemini
    default_model: gemini-2.5-pro
    capabilities: [code_gen, reasoning]
    enabled: true
defaults:
  exec: gemini-cli
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        monkeypatch.setattr(
            agent_config_module.AgentConfigService,
            "_detect_gemini_auth",
            lambda self: {
                "gemini_api_key_present": False,
                "google_api_key_present": False,
                "oauth_creds_present": True,
                "google_accounts_present": False,
                "google_application_credentials_present": False,
                "gcloud_adc_present": False,
            },
        )
        monkeypatch.setattr(
            agent_config_module.AgentConfigService,
            "_discover_gemini_models",
            lambda self, timeout=20: (
                ["auto", "flash", "gemini-2.5-pro"],
                "bundle",
                None,
                {},
            ),
        )

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                bad_model = client.post(
                    "/agents/gemini-cli/test",
                    json={"overrides": {"default_model": "not-a-real-gemini-model"}},
                )
                assert bad_model.status_code == 200
                payload = bad_model.json()
                checks = {item["name"]: item for item in payload["checks"]}
                assert checks["auth"]["ok"] is True
                assert checks["model"]["ok"] is False

                bad_reasoning = client.post(
                    "/agents/gemini-cli/test",
                    json={"overrides": {"default_model": "gemini-2.5-pro", "reasoning_effort": "high"}},
                )
                assert bad_reasoning.status_code == 200
                payload = bad_reasoning.json()
                checks = {item["name"]: item for item in payload["checks"]}
                assert checks["model"]["ok"] is True
                assert checks["reasoning_effort"]["ok"] is False

                save_resp = client.put(
                    "/agents/gemini-cli/config",
                    json={"default_model": "gemini-2.5-pro", "reasoning_effort": "high"},
                )
                assert save_resp.status_code == 400
                assert "does not expose configurable reasoning_effort" in save_resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_opencode_setup_fails_for_invalid_model_and_reasoning(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: openai/gpt-5-nano
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["opencode", "--version"]:
                return Result(0, stdout="opencode 0.1.0\n")
            if args == ["opencode", "auth", "list"]:
                return Result(0, stdout="1 credentials\n")
            if args == ["opencode", "models", "--verbose"]:
                return Result(0, stdout=OPENCODE_VERBOSE_MODELS)
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    "/agents/opencode/test",
                    json={"overrides": {"default_model": "zai-coding-plan/glm-5", "reasoning_effort": "max"}},
                )
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["ok"] is False
                checks = {c["name"]: c for c in payload["checks"]}
                assert checks["credentials"]["ok"] is True
                assert checks["model"]["ok"] is False
                assert "zai-coding-plan/glm-5" in (checks["model"]["error"] or "")
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_update_agent_config_rejects_invalid_opencode_reasoning_effort(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: openai/gpt-5-nano
    reasoning_effort: medium
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["opencode", "models", "--verbose"]:
                return Result(0, stdout=OPENCODE_VERBOSE_MODELS)
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.put("/agents/opencode/config", json={"reasoning_effort": "max"})
                assert resp.status_code == 400
                assert "Invalid reasoning_effort" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_opencode_models_endpoint_ignores_provider_error_output(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: zai-coding-plan/glm-5
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["opencode", "models", "--verbose"]:
                return Result(1, stderr="\x1b[91m\x1b[1mError: \x1b[0mProvider not found: zai-coding-plan\n")
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents/opencode/models")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["source"] == "cli"
                assert payload["models"] == []
                assert "Provider not found" in (payload["warning"] or "")
                assert "zai-coding-plan" not in " ".join(payload["models"])
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_opencode_models_endpoint_does_not_echo_invalid_configured_model(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "agents.yaml"
        config_path.write_text(
            """
agents:
  opencode:
    name: OpenCode
    kind: cli
    command: opencode
    default_model: zai-coding-plan/glm-5
    capabilities: [code_gen]
    enabled: true
defaults:
  exec: opencode
""".strip()
        )
        monkeypatch.setenv("DEVGODZILLA_AGENT_CONFIG_PATH", str(config_path))
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db

        import devgodzilla.services.agent_config as agent_config_module

        def fake_run(args, capture_output, text, timeout, check=False):  # noqa: ANN001
            class Result:
                def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            if args == ["opencode", "models", "--verbose"]:
                return Result(0, stdout=OPENCODE_VERBOSE_MODELS)
            raise AssertionError(f"Unexpected command: {args}")

        monkeypatch.setattr(agent_config_module.subprocess, "run", fake_run)

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get("/agents/opencode/models")
                assert resp.status_code == 200
                payload = resp.json()
                assert "zai-coding-plan/glm-5" not in payload["models"]
                assert payload["models"] == [
                    "openai/gpt-5-nano",
                    "openai/gpt-4.1",
                    "anthropic/claude-sonnet-4",
                ]
        finally:
            app.dependency_overrides.clear()
