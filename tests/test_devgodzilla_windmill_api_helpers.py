from __future__ import annotations

import sys
import types

from windmill.scripts.devgodzilla import _api
from windmill.scripts.devgodzilla import complete_sprint_api
from windmill.scripts.devgodzilla import onboard_to_tasks_api
from windmill.scripts.devgodzilla import sprint_from_protocol_api


def test_get_devgodzilla_api_base_url_prefers_windmill_variable(monkeypatch) -> None:
    monkeypatch.setenv("DEVGODZILLA_API_URL", "http://devgodzilla-api:8000")
    fake_wmill = types.SimpleNamespace(get_variable=lambda _name: "http://host.docker.internal:8000")
    monkeypatch.setitem(sys.modules, "wmill", fake_wmill)

    assert _api.get_devgodzilla_api_base_url() == "http://host.docker.internal:8000"


def test_get_devgodzilla_api_base_url_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.delenv("DEVGODZILLA_API_URL", raising=False)
    monkeypatch.delitem(sys.modules, "wmill", raising=False)
    monkeypatch.setenv("DEVGODZILLA_API_URL", "http://devgodzilla-api:8000")

    assert _api.get_devgodzilla_api_base_url() == "http://devgodzilla-api:8000"


def test_sprint_from_protocol_api_uses_shared_api_helper(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_api_json(method: str, path: str, *, body=None, timeout_seconds: int = 30):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        captured["timeout_seconds"] = timeout_seconds
        return {"id": 7, "name": "Sprint 7"}

    monkeypatch.setattr(sprint_from_protocol_api, "api_json", fake_api_json)

    result = sprint_from_protocol_api.main(
        12,
        sprint_name="Sprint 7",
        auto_sync=False,
        start_date="2026-03-09",
        end_date="2026-03-23",
    )

    assert result == {"id": 7, "name": "Sprint 7"}
    assert captured == {
        "method": "POST",
        "path": "/protocols/12/actions/create-sprint",
        "body": {
            "sprint_name": "Sprint 7",
            "auto_sync": False,
            "start_date": "2026-03-09",
            "end_date": "2026-03-23",
        },
        "timeout_seconds": 30,
    }


def test_complete_sprint_api_uses_shared_api_helper(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_api_json(method: str, path: str, *, body=None, timeout_seconds: int = 30):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        captured["timeout_seconds"] = timeout_seconds
        return {"id": 5, "status": "completed"}

    monkeypatch.setattr(complete_sprint_api, "api_json", fake_api_json)

    result = complete_sprint_api.main(5)

    assert result == {"id": 5, "status": "completed"}
    assert captured == {
        "method": "POST",
        "path": "/sprints/5/actions/complete",
        "body": {},
        "timeout_seconds": 30,
    }


def test_onboard_to_tasks_api_uses_single_backend_passthrough(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_api_json(method: str, path: str, *, body=None, timeout_seconds: int = 30):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        captured["timeout_seconds"] = timeout_seconds
        return {"project_id": 7}

    monkeypatch.setattr(onboard_to_tasks_api, "api_json", fake_api_json)

    result = onboard_to_tasks_api.main(
        git_url="https://github.com/example/repo.git",
        project_name="Example",
        branch="main",
        description="desc",
        constitution_content="constitution",
        feature_request="add feature",
        feature_name="feature",
        clarification_entries=[{"question": "Q", "answer": "A"}],
        clarification_notes="notes",
        run_discovery_agent=True,
        discovery_pipeline=False,
        discovery_engine_id="codex",
        discovery_model="gpt-5.4",
        clone_if_missing=False,
    )

    assert result == {"project_id": 7}
    assert captured == {
        "method": "POST",
        "path": "/projects/actions/onboard-to-tasks",
        "body": {
            "git_url": "https://github.com/example/repo.git",
            "project_name": "Example",
            "branch": "main",
            "description": "desc",
            "constitution_content": "constitution",
            "feature_request": "add feature",
            "feature_name": "feature",
            "clarification_entries": [{"question": "Q", "answer": "A"}],
            "clarification_notes": "notes",
            "run_discovery_agent": True,
            "discovery_pipeline": False,
            "discovery_engine_id": "codex",
            "discovery_model": "gpt-5.4",
            "clone_if_missing": False,
        },
        "timeout_seconds": 30,
    }
