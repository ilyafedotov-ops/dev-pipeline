from __future__ import annotations

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
def test_list_step_runs_returns_job_runs_for_step(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="completed",
            assigned_agent="opencode",
        )
        db.create_job_run(
            run_id="run-step-1",
            job_type="execute",
            status="succeeded",
            run_kind="engine",
            project_id=project.id,
            protocol_run_id=run.id,
            step_run_id=step.id,
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.get(f"/steps/{step.id}/runs")
                assert response.status_code == 200
                payload = response.json()
                assert len(payload) == 1
                assert payload[0]["run_id"] == "run-step-1"
                assert payload[0]["step_run_id"] == step.id
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_protocol_sprint_filters_protocol_linked_tasks_without_db_specific_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        sprint = db.create_sprint(project.id, "Sprint 1", status="active")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
        )
        db.create_task(
            project_id=project.id,
            title="Linked task",
            sprint_id=sprint.id,
            protocol_run_id=run.id,
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.get(f"/protocols/{run.id}/sprint")
                assert response.status_code == 200
                payload = response.json()
                assert payload is not None
                assert payload["id"] == sprint.id
                assert payload["name"] == "Sprint 1"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_link_protocol_to_sprint_persists_explicit_protocol_link_without_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        sprint = db.create_sprint(project.id, "Sprint Link", status="active")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                link_response = client.post(
                    f"/sprints/{sprint.id}/actions/link-protocol",
                    json={"protocol_run_id": run.id, "auto_sync": False},
                )
                sprint_response = client.get(f"/protocols/{run.id}/sprint")
                protocol_response = client.get(f"/protocols/{run.id}")

            assert link_response.status_code == 200
            assert sprint_response.status_code == 200
            assert protocol_response.status_code == 200

            payload = sprint_response.json()
            assert payload is not None
            assert payload["id"] == sprint.id
            assert payload["name"] == "Sprint Link"
            assert protocol_response.json()["linked_sprint_id"] == sprint.id
            assert db.get_protocol_run(run.id).linked_sprint_id == sprint.id
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_create_sprint_from_protocol_persists_explicit_protocol_link_without_auto_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                create_response = client.post(
                    f"/protocols/{run.id}/actions/create-sprint",
                    json={"auto_sync": False},
                )
                assert create_response.status_code == 200
                sprint_payload = create_response.json()
                sprint_response = client.get(f"/protocols/{run.id}/sprint")
                protocol_response = client.get(f"/protocols/{run.id}")

            assert sprint_response.status_code == 200
            assert protocol_response.status_code == 200
            assert sprint_response.json()["id"] == sprint_payload["id"]
            assert protocol_response.json()["linked_sprint_id"] == sprint_payload["id"]
            assert db.get_protocol_run(run.id).linked_sprint_id == sprint_payload["id"]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_step_quality_surfaces_skipped_gates_as_skipped_and_not_full_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="completed",
            assigned_agent="opencode",
        )
        db.create_qa_result(
            project_id=project.id,
            protocol_run_id=run.id,
            step_run_id=step.id,
            verdict="pass",
            summary="PASS: partial QA",
            gate_results=[
                {"gate_id": "prompt_qa", "gate_name": "Prompt QA", "verdict": "skip", "findings": []},
                {"gate_id": "lint", "gate_name": "Lint Gate", "verdict": "skip", "findings": []},
                {"gate_id": "test", "gate_name": "Test Gate", "verdict": "pass", "findings": []},
            ],
            findings=[],
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.get(f"/steps/{step.id}/quality")
                assert response.status_code == 200
                payload = response.json()
                assert payload["overall_status"] == "warning"
                assert payload["score"] == pytest.approx(1 / 3)
                statuses = {gate["article"]: gate["status"] for gate in payload["gates"]}
                assert statuses["prompt_qa"] == "skipped"
                assert statuses["lint"] == "skipped"
                assert statuses["test"] == "passed"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_protocol_sync_to_sprint_requires_body_sprint_id_and_persists_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        sprint = db.create_sprint(project.id, "Sprint Sync", status="active")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                missing_response = client.post(f"/protocols/{run.id}/actions/sync-to-sprint", json={})
                sync_response = client.post(
                    f"/protocols/{run.id}/actions/sync-to-sprint",
                    json={"sprint_id": sprint.id},
                )
                sprint_response = client.get(f"/protocols/{run.id}/sprint")
                protocol_response = client.get(f"/protocols/{run.id}")

            assert missing_response.status_code == 422
            assert sync_response.status_code == 200
            assert sync_response.json()["sprint_id"] == sprint.id
            assert sync_response.json()["protocol_run_id"] == run.id
            assert sync_response.json()["tasks_synced"] == 1
            assert sprint_response.json()["id"] == sprint.id
            assert protocol_response.json()["linked_sprint_id"] == sprint.id

            tasks = db.list_tasks(step_run_id=step.id, limit=10)
            assert len(tasks) == 1
            assert tasks[0].sprint_id == sprint.id
            assert db.get_protocol_run(run.id).linked_sprint_id == sprint.id
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_get_protocol_exposes_canonical_protocol_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")
        sprint = db.create_sprint(project.id, "Sprint Canonical", status="active")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-protocol",
            status="running",
            base_branch="main",
            description="Canonical protocol description",
        )
        db.update_protocol_paths(
            run.id,
            worktree_path=str(tmp / "worktrees" / "demo"),
            protocol_root=str(tmp / "worktrees" / "demo" / ".devgodzilla" / "protocols" / "demo"),
        )
        db.update_protocol_template(
            run.id,
            template_config={"mode": "brownfield"},
            template_source={"kind": "builtin", "name": "brownfield/default"},
        )
        db.update_protocol_policy_audit(
            run.id,
            policy_pack_key="repo/default",
            policy_pack_version="1.2.3",
            policy_effective_hash="policy-hash",
            policy_effective_json={"mode": "warn"},
        )
        db.update_protocol_windmill(
            run.id,
            windmill_flow_id="flow-123",
            speckit_metadata={
                "spec_run_id": 91,
                "spec_hash": "abc123",
                "validation_status": "validated",
                "validated_at": "2026-03-09T10:00:00Z",
            },
        )
        db.update_protocol_linked_sprint(run.id, sprint.id)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.get(f"/protocols/{run.id}")

            assert response.status_code == 200
            payload = response.json()
            assert payload["description"] == "Canonical protocol description"
            assert payload["protocol_root"].endswith("/.devgodzilla/protocols/demo")
            assert payload["template_config"] == {"mode": "brownfield"}
            assert payload["template_source"] == {
                "kind": "builtin",
                "name": "brownfield/default",
            }
            assert payload["policy_pack_key"] == "repo/default"
            assert payload["policy_pack_version"] == "1.2.3"
            assert payload["policy_effective_hash"] == "policy-hash"
            assert payload["policy_effective_json"] == {"mode": "warn"}
            assert payload["windmill_flow_id"] == "flow-123"
            assert payload["speckit_metadata"] == {
                "spec_run_id": 91,
                "spec_hash": "abc123",
                "validation_status": "validated",
                "validated_at": "2026-03-09T10:00:00Z",
            }
            assert payload["linked_sprint_id"] == sprint.id
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_create_project_protocol_persists_template_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.post(
                    f"/projects/{project.id}/protocols",
                    json={
                        "protocol_name": "demo-protocol",
                        "base_branch": "main",
                        "template_source": "./templates/feature.yaml",
                    },
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["template_source"] == "./templates/feature.yaml"
            assert db.get_protocol_run(payload["id"]).template_source == "./templates/feature.yaml"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_create_global_protocol_persists_template_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.post(
                    "/protocols",
                    json={
                        "project_id": project.id,
                        "name": "demo-protocol",
                        "branch_name": "main",
                        "template": "./templates/global.yaml",
                        "inputs": {"mode": "brownfield"},
                    },
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["template_source"] == "./templates/global.yaml"
            assert payload["template_config"] == {"mode": "brownfield"}
            run = db.get_protocol_run(payload["id"])
            assert run.template_source == "./templates/global.yaml"
            assert run.template_config == {"mode": "brownfield"}
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_create_global_protocol_accepts_canonical_request_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.post(
                    "/protocols",
                    json={
                        "project_id": project.id,
                        "protocol_name": "canonical-protocol",
                        "description": "Canonical request shape",
                        "base_branch": "develop",
                        "template_source": "./templates/canonical.yaml",
                        "template_config": {"mode": "brownfield"},
                    },
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["protocol_name"] == "canonical-protocol"
            assert payload["base_branch"] == "develop"
            assert payload["template_source"] == "./templates/canonical.yaml"
            assert payload["template_config"] == {"mode": "brownfield"}
            run = db.get_protocol_run(payload["id"])
            assert run.protocol_name == "canonical-protocol"
            assert run.base_branch == "develop"
            assert run.template_source == "./templates/canonical.yaml"
            assert run.template_config == {"mode": "brownfield"}
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_create_project_protocol_accepts_legacy_aliases_for_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(name="demo", git_url="git@example.com:demo/repo.git", base_branch="main")

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                response = client.post(
                    f"/projects/{project.id}/protocols",
                    json={
                        "name": "legacy-project-protocol",
                        "branch_name": "release",
                        "template": "./templates/legacy.yaml",
                        "inputs": {"mode": "guided"},
                    },
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["protocol_name"] == "legacy-project-protocol"
            assert payload["base_branch"] == "release"
            assert payload["template_source"] == "./templates/legacy.yaml"
            assert payload["template_config"] == {"mode": "guided"}
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()
