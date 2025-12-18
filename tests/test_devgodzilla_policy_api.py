"""
Tests for DevGodzilla Policy API endpoints.

Tests policy configuration, effective policy resolution, and findings.
"""

import json
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from devgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_project_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/policy returns policy configuration."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create project with policy configuration
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        
        # Update policy settings
        db.update_project_policy(
            project.id,
            policy_enforcement_mode="block",
            policy_repo_local_enabled=True,
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/projects/{project.id}/policy")
            assert response.status_code == 200
            
            data = response.json()
            assert data["policy_pack_key"] == "default"
            assert data["policy_pack_version"] == "1.0"
            assert data["policy_enforcement_mode"] == "block"
            assert data["policy_repo_local_enabled"] is True


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_update_project_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PUT /projects/{id}/policy updates policy configuration."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Update policy configuration
            update_data = {
                "policy_pack_key": "strict",
                "policy_pack_version": "2.0",
                "policy_enforcement_mode": "block",
                "policy_repo_local_enabled": True,
                "policy_overrides": {
                    "enforcement": {
                        "mode": "block"
                    }
                }
            }
            
            response = client.put(
                f"/projects/{project.id}/policy",
                json=update_data
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["policy_pack_key"] == "strict"
            assert data["policy_pack_version"] == "2.0"
            assert data["policy_enforcement_mode"] == "block"
            assert data["policy_repo_local_enabled"] is True
            assert data["policy_overrides"] is not None


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_effective_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/policy/effective returns computed policy with hash."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create a policy pack
        pack = db.upsert_policy_pack(
            key="default",
            version="1.0",
            name="Default Policy",
            status="active",
            pack={
                "meta": {"key": "default", "version": "1.0"},
                "enforcement": {"mode": "warn"},
                "requirements": {
                    "protocol_files": ["README.md"]
                }
            }
        )

        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_pack_key="default",
            policy_pack_version="1.0",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/projects/{project.id}/policy/effective")
            assert response.status_code == 200
            
            data = response.json()
            assert "hash" in data
            assert "policy" in data
            assert data["pack_key"] == "default"
            assert data["pack_version"] == "1.0"
            assert isinstance(data["policy"], dict)
            # Hash should be a non-empty string
            assert len(data["hash"]) > 0


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_policy_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/policy/findings returns policy violations."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create project without git_url (should trigger finding)
        project = db.create_project(
            name="demo",
            git_url="",  # Missing git_url
            base_branch="main",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/projects/{project.id}/policy/findings")
            assert response.status_code == 200
            
            findings = response.json()
            assert isinstance(findings, list)
            
            # Should have finding about missing git_url
            git_url_findings = [
                f for f in findings 
                if f["code"] == "policy.project.missing_git_url"
            ]
            assert len(git_url_findings) > 0
            assert git_url_findings[0]["severity"] == "error"
            assert git_url_findings[0]["scope"] == "project"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_policy_endpoints_404_for_missing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test policy endpoints return 404 for non-existent projects."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Test GET policy
            response = client.get("/projects/99999/policy")
            assert response.status_code == 404
            
            # Test PUT policy
            response = client.put(
                "/projects/99999/policy",
                json={"policy_pack_key": "test"}
            )
            assert response.status_code == 404
            
            # Test GET effective
            response = client.get("/projects/99999/policy/effective")
            assert response.status_code == 404
            
            # Test GET findings
            response = client.get("/projects/99999/policy/findings")
            assert response.status_code == 404


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_effective_policy_hash_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that effective policy hash changes when policy changes."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create a policy pack
        db.upsert_policy_pack(
            key="default",
            version="1.0",
            name="Default Policy",
            status="active",
            pack={
                "meta": {"key": "default", "version": "1.0"},
                "enforcement": {"mode": "warn"},
            }
        )

        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_pack_key="default",
            policy_pack_version="1.0",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Get initial hash
            response1 = client.get(f"/projects/{project.id}/policy/effective")
            assert response1.status_code == 200
            hash1 = response1.json()["hash"]
            
            # Update policy overrides
            client.put(
                f"/projects/{project.id}/policy",
                json={
                    "policy_overrides": {
                        "enforcement": {"mode": "block"}
                    }
                }
            )
            
            # Get new hash
            response2 = client.get(f"/projects/{project.id}/policy/effective")
            assert response2.status_code == 200
            hash2 = response2.json()["hash"]
            
            # Hashes should be different
            assert hash1 != hash2
