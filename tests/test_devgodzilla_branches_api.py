"""
Tests for DevGodzilla Project Branches API endpoint.

Tests branch listing for projects with git repositories.
"""

import subprocess
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
def test_list_project_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/branches returns list of branches."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        # Initialize a git repository with branches
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        
        # Create initial commit
        (repo / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        
        # Create a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "feature.txt").write_text("feature")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add feature"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        
        # Switch back to main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

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
            response = client.get(f"/projects/{project.id}/branches")
            assert response.status_code == 200
            
            branches = response.json()
            assert isinstance(branches, list)
            assert len(branches) >= 2  # At least main and feature/test
            
            # Check branch structure
            for branch in branches:
                assert "name" in branch
                assert "sha" in branch
                assert "is_remote" in branch
                assert isinstance(branch["name"], str)
                assert isinstance(branch["sha"], str)
                assert isinstance(branch["is_remote"], bool)
            
            # Verify we have the expected branches
            branch_names = [b["name"] for b in branches]
            assert "main" in branch_names
            assert "feature/test" in branch_names


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_list_branches_404_for_missing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/branches returns 404 for non-existent project."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get("/projects/99999/branches")
            assert response.status_code == 404


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_list_branches_400_for_missing_local_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/branches returns 400 when project has no local_path."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create project without local_path
        project = db.create_project(
            name="demo",
            git_url="https://github.com/example/repo.git",
            base_branch="main",
            local_path=None,
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/projects/{project.id}/branches")
            assert response.status_code == 400
            assert "no local repository path" in response.json()["detail"].lower()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_list_branches_400_for_nonexistent_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/branches returns 400 when local_path doesn't exist."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create project with non-existent local_path
        project = db.create_project(
            name="demo",
            git_url="https://github.com/example/repo.git",
            base_branch="main",
            local_path="/nonexistent/path",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            response = client.get(f"/projects/{project.id}/branches")
            assert response.status_code == 400
            assert "does not exist" in response.json()["detail"].lower()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_list_branches_400_for_non_git_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GET /projects/{id}/branches returns 400 when path is not a git repo."""
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        # Don't initialize git - just a regular directory

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
            response = client.get(f"/projects/{project.id}/branches")
            assert response.status_code == 400
            assert "not a git repository" in response.json()["detail"].lower()
