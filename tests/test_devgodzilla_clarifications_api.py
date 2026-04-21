"""
Tests for clarifications API routes.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

from devgodzilla.api.app import app
from devgodzilla.db.database import SQLiteDatabase


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
class TestClarificationsAPI:
    """Tests for /clarifications endpoints."""

    @pytest.fixture
    def db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        return db

    @pytest.fixture
    def client(self, db: SQLiteDatabase):
        from devgodzilla.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as c:
                yield c
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def sample_project(self, db: SQLiteDatabase):
        return db.create_project(
            name="Test Project",
            git_url="https://github.com/example/test.git",
            base_branch="main",
        )

    @pytest.fixture
    def sample_protocol(self, db: SQLiteDatabase, sample_project):
        return db.create_protocol_run(
            project_id=sample_project.id,
            protocol_name="test-protocol",
            status="running",
            base_branch="main",
        )

    @pytest.fixture
    def sample_clarification(self, db: SQLiteDatabase, sample_project):
        return db.upsert_clarification(
            scope=f"project:{sample_project.id}",
            project_id=sample_project.id,
            protocol_run_id=None,
            step_run_id=None,
            key="data_classification",
            question="What data classification applies to this project?",
            recommended={"value": "internal"},
            options=["public", "internal", "confidential"],
            applies_to="onboarding",
            blocking=True,
        )

    def test_list_clarifications_empty(self, client):
        """Test listing clarifications when none exist."""
        resp = client.get("/clarifications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_clarifications_with_data(
        self, client, sample_clarification
    ):
        """Test listing clarifications returns existing items."""
        resp = client.get("/clarifications")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "data_classification"
        assert data[0]["status"] == "open"

    def test_list_clarifications_filter_by_project(
        self, client, sample_project, sample_clarification
    ):
        """Test filtering clarifications by project_id."""
        resp = client.get(f"/clarifications?project_id={sample_project.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        # Non-matching project
        resp = client.get("/clarifications?project_id=9999")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_clarifications_filter_by_status(
        self, client, sample_project, db
    ):
        """Test filtering clarifications by status."""
        # Create two clarifications, answer one
        c1 = db.upsert_clarification(
            scope=f"project:{sample_project.id}",
            project_id=sample_project.id,
            key="q1",
            question="Question 1?",
            applies_to="test",
        )
        db.upsert_clarification(
            scope=f"project:{sample_project.id}",
            project_id=sample_project.id,
            key="q2",
            question="Question 2?",
            applies_to="test",
        )
        # Answer c1
        db.answer_clarification(
            scope=f"project:{sample_project.id}",
            key="q1",
            answer={"text": "Answer 1"},
            answered_by="test_user",
            status="answered",
        )

        resp = client.get("/clarifications?status=open")
        assert resp.status_code == 200
        open_items = resp.json()
        assert len(open_items) == 1
        assert open_items[0]["key"] == "q2"

        resp = client.get("/clarifications?status=answered")
        assert resp.status_code == 200
        answered = resp.json()
        assert len(answered) == 1
        assert answered[0]["key"] == "q1"

    def test_list_clarifications_limit(self, client, sample_project, db):
        """Test limit parameter."""
        for i in range(5):
            db.upsert_clarification(
                scope=f"project:{sample_project.id}",
                project_id=sample_project.id,
                key=f"q{i}",
                question=f"Question {i}?",
                applies_to="test",
            )

        resp = client.get("/clarifications?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_answer_clarification_success(
        self, client, sample_project, sample_clarification
    ):
        """Test answering a clarification."""
        resp = client.post(
            f"/clarifications/{sample_clarification.id}/answer",
            json={"answer": "internal", "answered_by": "test_user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"
        assert data["answer"]["text"] == "internal"
        assert data["answered_by"] == "test_user"

    def test_answer_clarification_not_found(self, client):
        """Test answering a non-existent clarification."""
        resp = client.post(
            "/clarifications/99999/answer",
            json={"answer": "test", "answered_by": "user"},
        )
        assert resp.status_code == 404

    def test_answer_clarification_protocol_scoped(
        self, client, sample_project, sample_protocol, db
    ):
        """Test answering a protocol-scoped clarification."""
        clarification = db.upsert_clarification(
            scope=f"protocol:{sample_protocol.id}",
            project_id=sample_project.id,
            protocol_run_id=sample_protocol.id,
            key="branch_strategy",
            question="Should we use feature branches?",
            applies_to="planning",
        )

        resp = client.post(
            f"/clarifications/{clarification.id}/answer",
            json={"answer": "yes, use feature/* pattern", "answered_by": "lead"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"

    def test_answer_project_clarification_route(self, client, sample_project, db):
        """Project-scoped answer route should persist normalized answer payloads."""
        db.upsert_clarification(
            scope=f"project:{sample_project.id}",
            project_id=sample_project.id,
            key="release_window",
            question="Which release window should be used?",
            applies_to="onboarding",
            blocking=True,
        )

        resp = client.post(
            f"/projects/{sample_project.id}/clarifications/release_window",
            json={"answer": "weekday evenings", "answered_by": "owner"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"
        assert data["answer"]["text"] == "weekday evenings"
        assert data["answered_by"] == "owner"

    def test_answer_protocol_clarification_route(self, client, sample_project, sample_protocol, db):
        """Protocol-scoped answer route should delegate through the shared clarifier flow."""
        db.upsert_clarification(
            scope=f"protocol:{sample_protocol.id}",
            project_id=sample_project.id,
            protocol_run_id=sample_protocol.id,
            key="protocol_owner",
            question="Who owns this protocol?",
            applies_to="planning",
            blocking=True,
        )

        resp = client.post(
            f"/protocols/{sample_protocol.id}/clarifications/protocol_owner",
            json={"answer": "platform team", "answered_by": "lead"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"
        assert data["answer"]["text"] == "platform team"
        assert data["answered_by"] == "lead"
