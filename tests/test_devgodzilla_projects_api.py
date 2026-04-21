from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    TestClient = None  # type: ignore

from devgodzilla.api.app import app
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import SQLiteDatabase


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_project_create_and_update_mask_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteDatabase(Path(tmpdir) / "test.db")
        db.init_schema()
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                create_resp = client.post(
                    "/projects",
                    json={
                        "name": "private-repo",
                        "git_url": "https://github.com/example/private.git",
                        "base_branch": "main",
                        "github_token": "ghp_create_secret",
                        "auto_onboard": False,
                        "auto_discovery": False,
                    },
                )
                assert create_resp.status_code == 200
                create_payload = create_resp.json()
                assert create_payload["github_token_configured"] is True
                assert "github_token" not in create_payload

                project = db.get_project(create_payload["id"])
                assert project.secrets == {"github_token": "ghp_create_secret"}

                update_resp = client.put(
                    f"/projects/{project.id}",
                    json={"github_token": "ghp_updated_secret"},
                )
                assert update_resp.status_code == 200
                update_payload = update_resp.json()
                assert update_payload["github_token_configured"] is True
                assert "github_token" not in update_payload

                project = db.get_project(project.id)
                assert project.secrets == {"github_token": "ghp_updated_secret"}

                clear_resp = client.put(
                    f"/projects/{project.id}",
                    json={"github_token": None},
                )
                assert clear_resp.status_code == 200
                clear_payload = clear_resp.json()
                assert clear_payload["github_token_configured"] is False
                assert "github_token" not in clear_payload

                project = db.get_project(project.id)
                assert project.secrets is None
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_project_create_uses_classification_driven_policy_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteDatabase(Path(tmpdir) / "test.db")
        db.init_schema()
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        app.dependency_overrides[get_db] = lambda: db

        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                create_resp = client.post(
                    "/projects",
                    json={
                        "name": "enterprise-project",
                        "git_url": "https://github.com/example/enterprise.git",
                        "base_branch": "main",
                        "project_classification": "enterprise-compliance",
                        "policy_enforcement_mode": "off",
                        "auto_onboard": False,
                        "auto_discovery": False,
                    },
                )
                assert create_resp.status_code == 200
                payload = create_resp.json()
                assert payload["project_classification"] == "enterprise-compliance"
                assert payload["policy_pack_key"] == "enterprise-compliance"
                assert payload["policy_pack_version"] == "1.0"
                assert payload["policy_enforcement_mode"] is None

                policy_resp = client.get(f"/projects/{payload['id']}/policy")
                assert policy_resp.status_code == 200
                policy_payload = policy_resp.json()
                assert policy_payload["policy_pack_key"] == "enterprise-compliance"
                assert policy_payload["policy_pack_version"] == "1.0"
                assert policy_payload["policy_enforcement_mode"] == "off"
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_onboarding_uses_project_github_token_for_clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = SQLiteDatabase(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project(
        name="private-repo",
        git_url="https://github.com/example/private.git",
        base_branch="main",
        secrets={"github_token": "ghp_onboard_secret"},
    )
    monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)
    monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
    app.dependency_overrides[get_db] = lambda: db

    captured: dict[str, str | None] = {"github_token": None}

    def fake_resolve_repo_path(self, git_url, project_name, local_path, **kwargs):
        captured["github_token"] = kwargs.get("github_token")
        repo_root = tmp_path / "repo"
        repo_root.mkdir(exist_ok=True)
        return repo_root

    def fake_init_project(self, repo_root, constitution_content=None, project_id=None):
        return SimpleNamespace(
            success=True,
            spec_path=str(Path(repo_root) / ".specify"),
            constitution_hash="abc123",
            warnings=[],
            error=None,
        )

    monkeypatch.setattr("devgodzilla.services.git.GitService.resolve_repo_path", fake_resolve_repo_path)
    monkeypatch.setattr("devgodzilla.services.specification.SpecificationService.init_project", fake_init_project)

    try:
        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                f"/projects/{project.id}/actions/onboard",
                json={"clone_if_missing": True, "run_discovery_agent": False},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["success"] is True
            assert captured["github_token"] == "ghp_onboard_secret"
    finally:
        app.dependency_overrides.clear()
