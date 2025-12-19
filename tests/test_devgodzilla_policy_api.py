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
def test_update_project_policy_normalizes_enforcement_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PUT /projects/{id}/policy normalizes enforcement mode values."""
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
            response = client.put(
                f"/projects/{project.id}/policy",
                json={"policy_enforcement_mode": "mandatory"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["policy_enforcement_mode"] == "block"


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


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_step_policy_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /steps/{id}/policy/findings returns step policy findings."""
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
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="planned",
            base_branch="main",
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=0,
            step_name="Setup",
            step_type="plan",
            status="pending",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/steps/{step.id}/policy/findings")
            assert response.status_code == 200
            findings = response.json()
            assert isinstance(findings, list)


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


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_list_policy_packs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /policy_packs returns list of policy packs."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create test policy packs
        pack1 = db.upsert_policy_pack(
            key="test1",
            version="1.0",
            name="Test Pack 1",
            description="First test pack",
            status="active",
            pack={"test": "data1"}
        )
        
        pack2 = db.upsert_policy_pack(
            key="test2",
            version="2.0",
            name="Test Pack 2",
            description="Second test pack",
            status="active",
            pack={"test": "data2"}
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get("/policy_packs")
            assert response.status_code == 200
            
            packs = response.json()
            assert isinstance(packs, list)
            assert len(packs) >= 2  # At least our test packs plus any defaults
            
            # Find our test packs
            test_pack_keys = {pack["key"] for pack in packs}
            assert "test1" in test_pack_keys
            assert "test2" in test_pack_keys


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_create_policy_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test POST /policy_packs creates a new policy pack."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            pack_data = {
                "key": "new-pack",
                "version": "1.0",
                "name": "New Policy Pack",
                "description": "A newly created pack",
                "status": "active",
                "pack": {
                    "meta": {"key": "new-pack", "version": "1.0"},
                    "enforcement": {"mode": "warn"}
                }
            }
            
            response = client.post("/policy_packs", json=pack_data)
            assert response.status_code == 200
            
            created_pack = response.json()
            assert created_pack["key"] == "new-pack"
            assert created_pack["version"] == "1.0"
            assert created_pack["name"] == "New Policy Pack"
            assert created_pack["description"] == "A newly created pack"
            assert created_pack["status"] == "active"
            assert created_pack["pack"]["meta"]["key"] == "new-pack"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_policy_pack_by_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /policy_packs/{key} returns latest active version."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create multiple versions of the same pack
        pack_v1 = db.upsert_policy_pack(
            key="versioned-pack",
            version="1.0",
            name="Versioned Pack v1",
            status="active",
            pack={"version": "1.0"}
        )
        
        pack_v2 = db.upsert_policy_pack(
            key="versioned-pack",
            version="2.0",
            name="Versioned Pack v2",
            status="active",
            pack={"version": "2.0"}
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Get latest version by key only
            response = client.get("/policy_packs/versioned-pack")
            assert response.status_code == 200
            
            pack = response.json()
            assert pack["key"] == "versioned-pack"
            # Should return the latest version (v2.0 was created after v1.0)
            assert pack["version"] == "2.0"
            assert pack["name"] == "Versioned Pack v2"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_policy_pack_by_key_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /policy_packs/{key}/{version} returns specific version."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create multiple versions
        pack_v1 = db.upsert_policy_pack(
            key="versioned-pack",
            version="1.0",
            name="Versioned Pack v1",
            status="active",
            pack={"version": "1.0"}
        )
        
        pack_v2 = db.upsert_policy_pack(
            key="versioned-pack",
            version="2.0",
            name="Versioned Pack v2",
            status="active",
            pack={"version": "2.0"}
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Get specific version
            response = client.get("/policy_packs/versioned-pack/1.0")
            assert response.status_code == 200
            
            pack = response.json()
            assert pack["key"] == "versioned-pack"
            assert pack["version"] == "1.0"
            assert pack["name"] == "Versioned Pack v1"
            assert pack["pack"]["version"] == "1.0"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_policy_pack_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test policy pack endpoints return 404 for non-existent packs."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Test GET by key only
            response = client.get("/policy_packs/nonexistent")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
            
            # Test GET by key and version
            response = client.get("/policy_packs/nonexistent/1.0")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_list_policy_packs_with_status_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /policy_packs with status filter."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create packs with different statuses
        active_pack = db.upsert_policy_pack(
            key="active-pack",
            version="1.0",
            name="Active Pack",
            status="active",
            pack={"test": "data"}
        )
        
        inactive_pack = db.upsert_policy_pack(
            key="inactive-pack",
            version="1.0",
            name="Inactive Pack",
            status="inactive",
            pack={"test": "data"}
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Test filter by active status
            response = client.get("/policy_packs?status=active")
            assert response.status_code == 200
            
            packs = response.json()
            assert isinstance(packs, list)
            
            # All returned packs should be active
            for pack in packs:
                assert pack["status"] == "active"
            
            # Should include our active pack
            active_keys = {pack["key"] for pack in packs}
            assert "active-pack" in active_keys
            assert "inactive-pack" not in active_keys


# =============================================================================
# Protocol Policy Endpoint Tests
# =============================================================================


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_protocol_policy_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /protocols/{id}/policy/findings returns policy violations for protocol."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create a policy pack with required protocol files
        db.upsert_policy_pack(
            key="default",
            version="1.0",
            name="Default Policy",
            status="active",
            pack={
                "meta": {"key": "default", "version": "1.0"},
                "requirements": {
                    "protocol_files": ["README.md", "DESIGN.md"]
                }
            }
        )

        # Create project with policy pack
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_pack_key="default",
            policy_pack_version="1.0",
        )

        # Create protocol run
        protocol = db.create_protocol_run(
            project_id=project.id,
            protocol_name="test-protocol",
            status="pending",
            base_branch="main",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/protocols/{protocol.id}/policy/findings")
            assert response.status_code == 200
            
            findings = response.json()
            assert isinstance(findings, list)
            # Findings should be a list (may be empty if no violations)
            for finding in findings:
                assert "code" in finding
                assert "severity" in finding
                assert "message" in finding
                assert "scope" in finding


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_protocol_policy_snapshot_with_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /protocols/{id}/policy/snapshot returns recorded policy audit."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create project
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )

        # Create protocol run
        protocol = db.create_protocol_run(
            project_id=project.id,
            protocol_name="test-protocol",
            status="pending",
            base_branch="main",
        )

        # Record policy audit on the protocol
        db.update_protocol_policy_audit(
            protocol.id,
            policy_pack_key="strict",
            policy_pack_version="2.0",
            policy_effective_hash="abc123def456",
            policy_effective_json={"enforcement": {"mode": "block"}},
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/protocols/{protocol.id}/policy/snapshot")
            assert response.status_code == 200
            
            data = response.json()
            assert data["hash"] == "abc123def456"
            assert data["pack_key"] == "strict"
            assert data["pack_version"] == "2.0"
            assert data["policy"]["enforcement"]["mode"] == "block"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_protocol_policy_snapshot_without_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /protocols/{id}/policy/snapshot resolves current policy when no audit exists."""
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

        # Create project with policy pack
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_pack_key="default",
            policy_pack_version="1.0",
        )

        # Create protocol run without policy audit
        protocol = db.create_protocol_run(
            project_id=project.id,
            protocol_name="test-protocol",
            status="pending",
            base_branch="main",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/protocols/{protocol.id}/policy/snapshot")
            assert response.status_code == 200
            
            data = response.json()
            assert "hash" in data
            assert len(data["hash"]) > 0
            assert data["pack_key"] == "default"
            assert data["pack_version"] == "1.0"
            assert "policy" in data
            assert isinstance(data["policy"], dict)


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_protocol_policy_endpoints_404_for_missing_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test protocol policy endpoints return 404 for non-existent protocols."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Test GET policy findings
            response = client.get("/protocols/99999/policy/findings")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            
            # Test GET policy snapshot
            response = client.get("/protocols/99999/policy/snapshot")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_protocol_policy_findings_with_missing_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that protocol policy findings include missing required files."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        
        # Create protocol directory without required files
        protocol_dir = repo / ".protocols" / "test-protocol"
        protocol_dir.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create a policy pack with required protocol files
        db.upsert_policy_pack(
            key="strict",
            version="1.0",
            name="Strict Policy",
            status="active",
            pack={
                "meta": {"key": "strict", "version": "1.0"},
                "requirements": {
                    "protocol_files": ["README.md", "DESIGN.md"]
                }
            }
        )

        # Create project with strict policy pack
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_pack_key="strict",
            policy_pack_version="1.0",
        )

        # Create protocol run with protocol_root set
        protocol = db.create_protocol_run(
            project_id=project.id,
            protocol_name="test-protocol",
            status="pending",
            base_branch="main",
        )
        
        # Update protocol with protocol_root
        db.update_protocol_paths(
            protocol.id,
            worktree_path=str(repo),
            protocol_root=str(protocol_dir),
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/protocols/{protocol.id}/policy/findings")
            assert response.status_code == 200
            
            findings = response.json()
            assert isinstance(findings, list)
            
            # Should have findings about missing protocol files
            missing_file_findings = [
                f for f in findings 
                if f["code"] == "policy.protocol.missing_file"
            ]
            # Should find at least one missing file (README.md or DESIGN.md)
            assert len(missing_file_findings) >= 1
            
            # Check finding structure
            for finding in missing_file_findings:
                assert finding["severity"] == "warning"
                assert finding["scope"] == "protocol"
                assert "suggested_fix" in finding
