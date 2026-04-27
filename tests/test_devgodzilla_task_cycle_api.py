import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from devgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True)
    (path / "README.md").write_text("demo", encoding="utf-8")
    (path / "AGENTS.md").write_text("# Guidance\n", encoding="utf-8")
    (path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (path / "tests").mkdir(exist_ok=True)
    (path / "tests" / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_build_context_creates_reusable_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_EXEC_ENGINE_ID", "opencode")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n- keep current behavior\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text(
            "# Add demo behavior\n\n- [ ] update README.md\n- [ ] add tests\n",
            encoding="utf-8",
        )
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["context_status"] == "ready"
                expected_task_dir = (repo / ".devgodzilla" / "task-cycle" / "protocols" / str(run.id) / "work-items" / str(step.id)).resolve()
                assert Path(payload["task_dir"]).resolve() == expected_task_dir
                context_path = Path(payload["artifact_refs"]["context_pack_json"])
                assert context_path.exists()
                assert context_path.resolve().is_relative_to(repo.resolve())
                assert not context_path.resolve().is_relative_to(projects_root.resolve())
                context = json.loads(context_path.read_text(encoding="utf-8"))
                assert context["project_id"] == project.id
                assert context["step_run_id"] == step.id
                assert any(item["path"] == "AGENTS.md" for item in context["style_guides"])
                assert any(command == "pytest -q" for command in context["test_commands"])
                assert payload["helper_agent_summary"] == "No helper subtasks configured under the owner"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_build_context_detects_nested_package_test_command(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        package_dir = repo / "packages" / "web"
        (package_dir / "src").mkdir(parents=True, exist_ok=True)
        (package_dir / "src" / "widget.tsx").write_text("export const Widget = () => null;\n", encoding="utf-8")
        (package_dir / "src" / "types.ts").write_text("export interface WidgetProps { enabled: boolean }\n", encoding="utf-8")
        (package_dir / "package.json").write_text(
            json.dumps(
                {
                    "name": "web",
                    "scripts": {
                        "test": "vitest run",
                    },
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_EXEC_ENGINE_ID", "opencode")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (repo / "schemas").mkdir(exist_ok=True)
        (repo / "schemas" / "widget.schema.json").write_text('{"type":"object"}\n', encoding="utf-8")
        (repo / "contracts").mkdir(exist_ok=True)
        (repo / "contracts" / "widget-api.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
        (protocol_root / "plan.md").write_text(
            "# Plan\n- update packages/web/src/widget.tsx\n- align contracts/widget-api.yaml\n- validate schemas/widget.schema.json\n",
            encoding="utf-8",
        )
        (protocol_root / "step-01-demo.md").write_text(
            "# Update widget\n\n- [ ] update packages/web/src/widget.tsx\n- [ ] update packages/web/src/types.ts\n- [ ] align contracts/widget-api.yaml\n- [ ] validate schemas/widget.schema.json\n- [ ] add tests\n",
            encoding="utf-8",
        )
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert resp.status_code == 200
                context_path = Path(resp.json()["artifact_refs"]["context_pack_json"])
                context = json.loads(context_path.read_text(encoding="utf-8"))
                assert "cd packages/web && npm test" in context["test_commands"]
                assert context["test_command_specs"][0] == {
                    "cwd": "packages/web",
                    "command": ["npm", "test"],
                    "display": "cd packages/web && npm test",
                }
                assert {
                    "cwd": "packages/web",
                    "command": ["npm", "test"],
                    "display": "cd packages/web && npm test",
                } in context["test_command_specs"]
                assert context["test_commands"][0] == "cd packages/web && npm test"
                assert {
                    "cwd": ".",
                    "command": ["pytest", "-q"],
                    "display": "pytest -q",
                } in context["test_command_specs"]
                assert any(item["path"] == "contracts/widget-api.yaml" for item in context["contracts"])
                assert any(item["path"] == "packages/web/src/types.ts" for item in context["types"])
                assert any(item["path"] == "schemas/widget.schema.json" for item in context["schemas"])
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_implement_blocks_when_context_needs_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_REVIEW_ENGINE_ID", "dummy")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text(
            "# Investigate setup\n\n- [ ] inspect current flow\n",
            encoding="utf-8",
        )
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                monkeypatch.setattr(
                    "devgodzilla.services.task_cycle.TaskCycleService._context_open_questions",
                    lambda self, entry_points, required_files, test_commands: [
                        "Need the primary module before execution."
                    ],
                )
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200
                assert context_resp.json()["context_status"] == "needs_clarification"
                assert context_resp.json()["blocking_clarifications"] > 0

                implement_resp = client.post(f"/work-items/{step.id}/actions/implement", json={})
                assert implement_resp.status_code == 409
                assert "ContextPack" in implement_resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_review_qa_and_pr_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.qa.gates.interface import GateResult, GateVerdict
    from devgodzilla.services.quality import QAResult, QAVerdict

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_REVIEW_ENGINE_ID", "dummy")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n\n- [ ] update README.md\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="completed",
            assigned_agent="dev",
        )
        artifacts_dir = protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "execution.log").write_text("implemented\n", encoding="utf-8")
        (artifacts_dir / "changes.diff").write_text("diff --git a/README.md b/README.md\n", encoding="utf-8")

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.PolicyService.evaluate_step",
            lambda self, step_run_id, repo_root=None: [],
        )

        qa_call = {}

        def _fake_run_qa(self, step_run_id, gates=None, skip_gates=None):
            qa_call["gate_ids"] = [gate.gate_id for gate in (gates or [])]
            qa_call["skip_gates"] = list(skip_gates or [])
            return QAResult(
                step_run_id=step_run_id,
                verdict=QAVerdict.PASS,
                gate_results=[
                    GateResult(gate_id="lint", gate_name="Lint", verdict=GateVerdict.PASS),
                ],
                duration_seconds=0.1,
            )

        monkeypatch.setattr("devgodzilla.services.task_cycle.QualityService.run_qa", _fake_run_qa)
        monkeypatch.setattr("devgodzilla.services.task_cycle.QualityService.persist_verdict", lambda self, qa_result, step_run_id, report_path=None: None)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200

                review_resp = client.post(f"/work-items/{step.id}/actions/review")
                assert review_resp.status_code == 200
                assert review_resp.json()["verdict"] == "passed"

                qa_resp = client.post(f"/work-items/{step.id}/actions/qa", json={"gates": ["lint"]})
                assert qa_resp.status_code == 200
                assert qa_resp.json()["qa"]["verdict"] == "passed"
                assert qa_resp.json()["work_item"]["status"] == "ready_for_pr"
                assert qa_call["gate_ids"] == ["lint"]
                assert qa_call["skip_gates"] == ["prompt_qa"]

                pr_resp = client.post(f"/work-items/{step.id}/actions/mark-pr-ready")
                assert pr_resp.status_code == 200
                assert pr_resp.json()["pr_ready"] is True
                assert pr_resp.json()["status"] == "pr_ready"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_work_item_exposes_helper_agent_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="codex",
        )
        db.update_step_run(
            step.id,
            runtime_state={
                "task_cycle": {
                    "owner_agent": "codex",
                    "helper_agents": ["trace", "tests"],
                }
            },
        )
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get(f"/work-items/{step.id}")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["helper_agents"] == ["trace", "tests"]
                assert "internal delegation only" in payload["helper_agent_summary"]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_work_item_summary_is_derived_from_state_not_stale_step_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="blocked",
            assigned_agent="codex",
        )
        db.update_step_status(step.id, "blocked", summary="QA passed")
        db.update_step_run(
            step.id,
            runtime_state={
                "task_cycle": {
                    "status": "blocked",
                    "context_status": "ready",
                    "review_status": "passed",
                    "qa_status": "pending",
                    "pr_ready": False,
                }
            },
        )
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get(f"/work-items/{step.id}")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["qa_status"] == "pending"
                assert payload["summary"] == "Step is blocked"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_implement_runs_helper_subtasks_without_creating_step_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.engines.interface import EngineResult
    from devgodzilla.models.domain import StepStatus
    from devgodzilla.services.execution import ExecutionResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_EXEC_ENGINE_ID", "opencode")
        monkeypatch.setenv("DEVGODZILLA_TASK_CYCLE_HELPER_PARALLELISM", "2")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(name="demo", git_url=str(repo), base_branch="main", local_path=str(repo))
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\nUpdate src/app.py\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text(
            "# Update demo\n\n- [ ] modify src/app.py\n- [ ] update tests/test_demo.py\n",
            encoding="utf-8",
        )
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )
        step = db.update_step_run(step.id, runtime_state={"task_cycle": {"helper_agents": ["trace", "tests"]}})

        def _fake_helper_execute(self, *, project_id, protocol_run_id, step_run_id, engine_id, prompt_text, working_dir):
            role = "trace" if "trace" in prompt_text.lower() else "tests"
            return EngineResult(success=True, stdout=f"{role} findings for owner", stderr="")

        def _fake_execute_step(self, step_run_id, **kwargs):
            self.db.update_step_status(step_run_id, StepStatus.COMPLETED, summary="owner complete")
            return ExecutionResult(success=True, step_run_id=step_run_id, engine_id="opencode")

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle_helpers.TaskCycleHelperRunner.execute_helper_prompt",
            _fake_helper_execute,
        )
        monkeypatch.setattr("devgodzilla.services.task_cycle.ExecutionService.execute_step", _fake_execute_step)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200

                implement_resp = client.post(f"/work-items/{step.id}/actions/implement", json={"owner_agent": "dev"})
                assert implement_resp.status_code == 200
                payload = implement_resp.json()
                assert payload["status"] == "awaiting_review"
                assert payload["helper_agent_summary"] == "2 helpers under the owner: 2 completed"

                helper_summary = repo / ".devgodzilla" / "task-cycle" / "protocols" / str(run.id) / "work-items" / str(step.id) / "helpers" / "helper_summary.json"
                assert helper_summary.exists()
                summary_payload = json.loads(helper_summary.read_text(encoding="utf-8"))
                assert len(summary_payload["helpers"]) == 2
                trace_result = helper_summary.parent / "trace" / "result.json"
                tests_result = helper_summary.parent / "tests" / "result.json"
                assert trace_result.exists()
                assert tests_result.exists()
                assert len(db.list_step_runs(run.id)) == 1
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_helper_subtasks_respect_parallelism_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.models.domain import StepStatus
    from devgodzilla.services.execution import ExecutionResult
    import threading
    import time

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_TASK_CYCLE_HELPER_PARALLELISM", "2")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(name="demo", git_url=str(repo), base_branch="main", local_path=str(repo))
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\nUpdate src/app.py\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text("# Update demo\n\n- [ ] modify src/app.py\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )
        step = db.update_step_run(
            step.id,
            runtime_state={"task_cycle": {"helper_agents": ["trace", "tests", "review", "docs"]}},
        )

        active = 0
        max_active = 0
        lock = threading.Lock()

        def _fake_helper_subtask(self, **kwargs):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            helper_agent = kwargs["helper_agent"]
            helper_dir = kwargs["helper_dir"]
            helper_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "helper_agent": helper_agent,
                "status": "completed",
                "engine_id": "opencode",
                "role": helper_agent,
                "artifact_dir": str(helper_dir),
                "summary": f"{helper_agent} complete",
            }
            (helper_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload

        def _fake_execute_step(self, step_run_id, **kwargs):
            self.db.update_step_status(step_run_id, StepStatus.COMPLETED, summary="owner complete")
            return ExecutionResult(success=True, step_run_id=step_run_id, engine_id="opencode")

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle_helpers.TaskCycleHelperRunner.execute_helper_subtask",
            _fake_helper_subtask,
        )
        monkeypatch.setattr("devgodzilla.services.task_cycle.ExecutionService.execute_step", _fake_execute_step)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200

                implement_resp = client.post(f"/work-items/{step.id}/actions/implement", json={"owner_agent": "dev"})
                assert implement_resp.status_code == 200
                assert max_active == 2
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_openapi_and_features_include_task_cycle_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.config import _reset_config_for_tests

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "devgodzilla.sqlite"
        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_TASK_CYCLE_ENABLED", "true")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        with TestClient(app) as client:  # type: ignore[arg-type]
            features_resp = client.get("/features")
            assert features_resp.status_code == 200
            assert features_resp.json()["task_cycle_enabled"] is True

            openapi_resp = client.get("/openapi.json")
            assert openapi_resp.status_code == 200
            paths = openapi_resp.json()["paths"]
            assert "/projects/{project_id}/brownfield/run" in paths
            assert "/projects/{project_id}/task-cycle" in paths
            assert "/work-items/{work_item_id}/artifacts/{artifact_key}/content" in paths
        _reset_config_for_tests()


@pytest.mark.integration
@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_start_brownfield_run_creates_protocol_and_work_items(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.services.specification import PlanResult, SpecifyResult, TasksResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        spec_dir = repo / "specs" / "001-demo-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / "spec.md"
        plan_path = spec_dir / "plan.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.write_text("# Demo feature\n", encoding="utf-8")
        plan_path.write_text("# Plan\n", encoding="utf-8")
        tasks_path.write_text(
            "## Phase 1\n- [ ] update README.md\n- [ ] add tests/test_demo.py\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        other_protocol_root = repo / "specs" / "other-protocol" / "_runtime"
        other_protocol_root.mkdir(parents=True, exist_ok=True)
        other_run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="other-protocol",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(other_protocol_root),
        )
        other_step = db.create_step_run(
            protocol_run_id=other_run.id,
            step_index=1,
            step_name="step-01-other",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_specify",
            lambda self, project_path, description, feature_name=None, base_branch=None, project_id=None: SpecifyResult(
                success=True,
                spec_path=str(spec_path),
                spec_number=1,
                feature_name="demo-feature",
                spec_run_id=None,
                worktree_path=str(repo),
                branch_name="001-demo-feature",
                base_branch="main",
                spec_root=str(spec_dir),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_plan",
            lambda self, project_path, spec_path, spec_run_id=None, project_id=None: PlanResult(
                success=True,
                plan_path=str(plan_path),
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_tasks",
            lambda self, project_path, plan_path, spec_run_id=None, project_id=None: TasksResult(
                success=True,
                tasks_path=str(tasks_path),
                task_count=2,
                parallelizable_count=0,
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )
        # Mock CLI execution to avoid hanging on real opencode subprocess
        monkeypatch.setattr(
            "devgodzilla.engines.cli_adapter.run_cli_command",
            lambda *a, **kw: __import__("devgodzilla.engines.cli_adapter", fromlist=["EngineResult"]).EngineResult(
                success=True,
                stdout="mocked cli output",
                stderr="",
                exit_code=0,
                duration_seconds=0.1,
            ),
        )
        # Mock ExecutionService.execute_step — it calls real CLI via engine adapter
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.ExecutionService",
            type(
                "MockExecutionService",
                (),
                {
                    "__init__": lambda self, ctx, db: None,
                    "execute_step": lambda self, step_run_id: None,
                },
            ),
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    f"/projects/{project.id}/brownfield/run",
                    json={
                        "feature_request": "Add demo behavior to the brownfield project",
                        "feature_name": "demo-feature",
                        "output_mode": "task_cycle",
                        "owner_agent": "dev",
                        "helper_agents": ["trace", "tests"],
                    },
                )
                assert resp.status_code in (200, 202)
                payload = resp.json()
                assert payload["success"] is True
                if resp.status_code == 200:
                    assert payload["protocol"] is not None
                    assert payload["next_work_item_id"] is not None
                    assert len(payload["work_items"]) == 1
                    assert payload["work_items"][0]["owner_agent"] == "opencode"
                    assert payload["work_items"][0]["helper_agents"] == ["trace", "tests"]

                listed = client.get(f"/projects/{project.id}/task-cycle")
                assert listed.status_code == 200
                if resp.status_code == 200:
                    listed_ids = [item["id"] for item in listed.json()]
                    assert payload["work_items"][0]["id"] in listed_ids
                    assert other_step.id not in listed_ids
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_brownfield_tasks_to_sprint_imports_generated_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.services.specification import PlanResult, SpecifyResult, TasksResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        spec_dir = repo / "specs" / "001-demo-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / "spec.md"
        plan_path = spec_dir / "plan.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.write_text("# Demo feature\n", encoding="utf-8")
        plan_path.write_text("# Plan\n", encoding="utf-8")
        tasks_path.write_text(
            "## Phase 1\n- [ ] update README.md\n- [ ] add tests/test_demo.py\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        sprint = db.create_sprint(project_id=project.id, name="Sprint 1", goal="Ship tasks", status="active")

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_specify",
            lambda self, project_path, description, feature_name=None, base_branch=None, project_id=None: SpecifyResult(
                success=True,
                spec_path=str(spec_path),
                spec_number=1,
                feature_name="demo-feature",
                spec_run_id=None,
                worktree_path=str(repo),
                branch_name="001-demo-feature",
                base_branch="main",
                spec_root=str(spec_dir),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_plan",
            lambda self, project_path, spec_path, spec_run_id=None, project_id=None: PlanResult(
                success=True,
                plan_path=str(plan_path),
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_tasks",
            lambda self, project_path, plan_path, spec_run_id=None, project_id=None: TasksResult(
                success=True,
                tasks_path=str(tasks_path),
                task_count=2,
                parallelizable_count=0,
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    f"/projects/{project.id}/brownfield/run",
                    json={
                        "feature_request": "Import generated tasks into a sprint",
                        "feature_name": "demo-feature",
                        "output_mode": "tasks_to_sprint",
                        "sprint_id": sprint.id,
                    },
                )
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["success"] is True
                assert payload["protocol"] is None
                assert payload["sprint"]["id"] == sprint.id
                assert payload["tasks_synced"] == 2
                assert len(payload["task_ids"]) == 2
                assert len(db.list_tasks(sprint_id=sprint.id)) == 2
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_brownfield_protocol_to_sprint_creates_sprint_and_syncs_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.services.specification import PlanResult, SpecifyResult, TasksResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        spec_dir = repo / "specs" / "001-demo-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / "spec.md"
        plan_path = spec_dir / "plan.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.write_text("# Demo feature\n", encoding="utf-8")
        plan_path.write_text("# Plan\n", encoding="utf-8")
        tasks_path.write_text(
            "## Phase 1\n- [ ] update README.md\n- [ ] add tests/test_demo.py\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_specify",
            lambda self, project_path, description, feature_name=None, base_branch=None, project_id=None: SpecifyResult(
                success=True,
                spec_path=str(spec_path),
                spec_number=1,
                feature_name="demo-feature",
                spec_run_id=None,
                worktree_path=str(repo),
                branch_name="001-demo-feature",
                base_branch="main",
                spec_root=str(spec_dir),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_plan",
            lambda self, project_path, spec_path, spec_run_id=None, project_id=None: PlanResult(
                success=True,
                plan_path=str(plan_path),
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_tasks",
            lambda self, project_path, plan_path, spec_run_id=None, project_id=None: TasksResult(
                success=True,
                tasks_path=str(tasks_path),
                task_count=2,
                parallelizable_count=0,
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    f"/projects/{project.id}/brownfield/run",
                    json={
                        "feature_request": "Create a sprint from the brownfield protocol",
                        "feature_name": "demo-feature",
                        "output_mode": "protocol_to_sprint",
                        "sprint_name": "Brownfield Sprint",
                    },
                )
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["success"] is True
                assert payload["protocol"] is not None
                assert payload["sprint"]["name"] == "Brownfield Sprint"
                assert payload["tasks_synced"] >= 1
                assert len(payload["task_ids"]) == payload["tasks_synced"]
                assert payload["work_items"] == []
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_failed_review_writes_rework_pack_and_exposes_artifact_content(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="failed",
            assigned_agent="dev",
        )

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.PolicyService.evaluate_step",
            lambda self, step_run_id, repo_root=None: [],
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200

                review_resp = client.post(f"/work-items/{step.id}/actions/review")
                assert review_resp.status_code == 200
                assert review_resp.json()["verdict"] == "failed"

                work_item_resp = client.get(f"/work-items/{step.id}")
                assert work_item_resp.status_code == 200
                rework_path = Path(work_item_resp.json()["artifact_refs"]["rework_pack_json"])
                assert rework_path.exists()
                rework = json.loads(rework_path.read_text(encoding="utf-8"))
                assert rework["source"] == "review"

                artifact_resp = client.get(f"/work-items/{step.id}/artifacts/rework_pack_json/content")
                assert artifact_resp.status_code == 200
                assert "\"source\": \"review\"" in artifact_resp.json()["content"]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_artifact_content_falls_back_to_step_quality_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="completed",
            assigned_agent="dev",
        )

        step_artifacts_dir = protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"
        step_artifacts_dir.mkdir(parents=True, exist_ok=True)
        (step_artifacts_dir / "quality-report.md").write_text(
            "# QA Report\n\nLegacy step-level QA artifact\n",
            encoding="utf-8",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                work_item_resp = client.get(f"/work-items/{step.id}")
                assert work_item_resp.status_code == 200
                payload = work_item_resp.json()
                assert payload["artifact_availability"]["test_report_md"] is True
                assert not Path(payload["artifact_refs"]["test_report_md"]).exists()

                artifact_resp = client.get(f"/work-items/{step.id}/artifacts/test_report_md/content")
                assert artifact_resp.status_code == 200
                assert "Legacy step-level QA artifact" in artifact_resp.json()["content"]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_review_uses_separate_review_agent_and_writes_review_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.engines.interface import Engine, EngineKind, EngineMetadata, EngineRequest, EngineResult
    from devgodzilla.engines.registry import _reset_registry_for_tests, get_registry

    class ReviewTestEngine(Engine):
        def __init__(self) -> None:
            self.requests: List[EngineRequest] = []

        @property
        def metadata(self) -> EngineMetadata:
            return EngineMetadata(id="reviewer", display_name="Reviewer", kind=EngineKind.CLI, default_model="review-model")

        def plan(self, req: EngineRequest) -> EngineResult:
            raise AssertionError("review test engine should not be used for planning")

        def execute(self, req: EngineRequest) -> EngineResult:
            raise AssertionError("review test engine should not be used for execution")

        def qa(self, req: EngineRequest) -> EngineResult:
            self.requests.append(req)
            return EngineResult(
                success=True,
                stdout=json.dumps(
                    {
                        "verdict": "passed",
                        "summary": "Dedicated review agent approved the work item",
                        "findings": [],
                        "required_rework": [],
                        "warnings": [],
                        "confidence": "high",
                    }
                ),
            )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_EXEC_ENGINE_ID", "opencode")
        monkeypatch.setenv("DEVGODZILLA_REVIEW_ENGINE_ID", "reviewer")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n- update README\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n- [ ] update README.md\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="completed",
            assigned_agent="dev",
        )
        artifacts_dir = protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "changes.diff").write_text("diff --git a/README.md b/README.md\n", encoding="utf-8")
        (artifacts_dir / "execution.log").write_text("implemented\n", encoding="utf-8")

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.PolicyService.evaluate_step",
            lambda self, step_run_id, repo_root=None: [],
        )

        _reset_registry_for_tests()
        engine = ReviewTestEngine()
        registry = get_registry()
        registry.register(engine, default=True)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200

                review_resp = client.post(f"/work-items/{step.id}/actions/review")
                assert review_resp.status_code == 200
                review_payload = review_resp.json()
                assert review_payload["verdict"] == "passed"
                assert review_payload["review_agent"] == "reviewer"
                assert review_payload["summary"] == "Dedicated review agent approved the work item"

                work_item_resp = client.get(f"/work-items/{step.id}")
                assert work_item_resp.status_code == 200
                work_item_payload = work_item_resp.json()
                assert work_item_payload["review_agent"] == "reviewer"

                review_input_path = Path(work_item_payload["artifact_refs"]["review_input_json"])
                assert review_input_path.exists()
                review_input = json.loads(review_input_path.read_text(encoding="utf-8"))
                assert review_input["context_pack"]["project_id"] == project.id
                assert review_input["context_pack"]["step_run_id"] == step.id
                assert review_input["diff_paths"]
                assert review_input["test_commands"]

                review_report_path = Path(work_item_payload["artifact_refs"]["review_report_json"])
                review_report = json.loads(review_report_path.read_text(encoding="utf-8"))
                assert review_report["review_agent"] == "reviewer"
                assert review_report["agent_report"]["confidence"] == "high"

                assert len(engine.requests) == 1
                assert "## Review Input" in (engine.requests[0].prompt_text or "")
                assert "\"context_pack\"" in (engine.requests[0].prompt_text or "")
        finally:
            app.dependency_overrides.clear()
            _reset_registry_for_tests()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_implement_respects_max_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.models.domain import StepStatus
    from devgodzilla.services.execution import ExecutionResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("DEVGODZILLA_TASK_CYCLE_MAX_ITERATIONS", "2")
        monkeypatch.setenv("DEVGODZILLA_EXEC_ENGINE_ID", "opencode")
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="pending",
            assigned_agent="dev",
        )

        def _fake_execute(self, step_run_id):
            self.db.update_step_status(step_run_id, StepStatus.FAILED, summary="forced failure")
            return ExecutionResult(success=False, step_run_id=step_run_id, engine_id="dummy", error="forced failure")

        monkeypatch.setattr("devgodzilla.services.task_cycle.ExecutionService.execute_step", _fake_execute)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context.status_code == 200
                first = client.post(f"/work-items/{step.id}/actions/implement", json={"owner_agent": "dev"})
                assert first.status_code == 200
                assert first.json()["iteration_count"] == 1

                second = client.post(f"/work-items/{step.id}/actions/implement", json={"owner_agent": "dev"})
                assert second.status_code == 200
                assert second.json()["iteration_count"] == 2

                third = client.post(f"/work-items/{step.id}/actions/implement", json={"owner_agent": "dev"})
                assert third.status_code == 409
                assert "Max task-cycle iterations reached" in third.json()["detail"]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_task_cycle_qa_requires_reviewable_implementation_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status="failed",
            assigned_agent="dev",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200

                qa_resp = client.post(f"/work-items/{step.id}/actions/qa", json={"gates": ["lint"]})
                assert qa_resp.status_code == 400
                assert "qa-ready state" in qa_resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
@pytest.mark.parametrize("step_status", ["failed", "timeout", "blocked"])
def test_task_cycle_derives_awaiting_review_for_terminal_step_statuses(
    monkeypatch: pytest.MonkeyPatch, step_status: str
) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        projects_root = tmp / "projects-root"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", str(projects_root))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)
        _reset_config_for_tests()

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        protocol_root = repo / "specs" / "demo-feature" / "_runtime"
        protocol_root.mkdir(parents=True, exist_ok=True)
        (protocol_root / "step-01-demo.md").write_text("# Demo step\n", encoding="utf-8")
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-feature",
            status="planned",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )
        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="step-01-demo",
            step_type="execute",
            status=step_status,
            assigned_agent="dev",
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.get(f"/work-items/{step.id}")
                assert resp.status_code == 200
                payload = resp.json()
                assert payload["status"] == "awaiting_review"
                assert payload["review_status"] == "pending"
                assert payload["qa_status"] == "pending"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


# ---------------------------------------------------------------------------
# Brownfield validation & missing-mode tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_brownfield_rejects_missing_local_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /projects/{id}/brownfield/run returns 400 when project has no local_path."""
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        # Create project WITHOUT local_path
        project = db.create_project(name="no-path", git_url="https://example.com/repo", base_branch="main")

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    f"/projects/{project.id}/brownfield/run",
                    json={
                        "feature_request": "Add hello",
                        "output_mode": "task_cycle",
                    },
                )
                assert resp.status_code == 400
                assert "no local path" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_brownfield_rejects_unknown_project() -> None:
    """POST /projects/{id}/brownfield/run returns 404 for non-existent project."""
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        db = SQLiteDatabase(db_path)
        db.init_schema()

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    "/projects/99999/brownfield/run",
                    json={
                        "feature_request": "Add hello",
                        "output_mode": "task_cycle",
                    },
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_brownfield_tasks_only_mode_returns_spec_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /projects/{id}/brownfield/run with output_mode=tasks_only returns spec info."""
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.services.specification import PlanResult, SpecifyResult, TasksResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        _init_repo(repo)

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="tasks-only-proj",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )

        spec_dir = repo / "specs" / "001-hello"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / "spec.md"
        plan_path = spec_dir / "plan.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.write_text("# Hello\n", encoding="utf-8")
        plan_path.write_text("# Plan\n", encoding="utf-8")
        tasks_path.write_text("# Tasks\n", encoding="utf-8")

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_specify",
            lambda self, project_path, description, feature_name=None, base_branch=None, project_id=None: SpecifyResult(
                success=True,
                spec_path=str(spec_path),
                spec_number=1,
                feature_name="hello",
                project_path=str(repo),
                base_branch="main",
                spec_root=str(spec_dir),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_plan",
            lambda self, project_path, spec_path, spec_run_id=None, project_id=None: PlanResult(
                success=True,
                plan_path=str(plan_path),
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_tasks",
            lambda self, project_path, plan_path, spec_run_id=None, project_id=None: TasksResult(
                success=True,
                tasks_path=str(tasks_path),
                task_count=1,
                parallelizable_count=0,
            ),
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    f"/projects/{project.id}/brownfield/run",
                    json={
                        "feature_request": "Add a hello endpoint",
                        "output_mode": "tasks_only",
                    },
                )
                assert resp.status_code in (200, 202)
                payload = resp.json()
                assert payload["success"] is True
                assert payload["output_mode"] == "tasks_only"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_brownfield_protocol_mode_returns_protocol_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /projects/{id}/brownfield/run with output_mode=protocol creates a protocol."""
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.services.specification import PlanResult, SpecifyResult, TasksResult

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        _init_repo(repo)

        db = SQLiteDatabase(db_path)
        db.init_schema()
        project = db.create_project(
            name="protocol-mode-proj",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )

        spec_dir = repo / "specs" / "001-hello"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / "spec.md"
        plan_path = spec_dir / "plan.md"
        tasks_path = spec_dir / "tasks.md"
        spec_path.write_text("# Hello\n", encoding="utf-8")
        plan_path.write_text("# Plan\n", encoding="utf-8")
        tasks_path.write_text(
            "# Tasks\n\n## Phase 1: Setup\n- [ ] T1: Create hello.py - Add hello endpoint\n\n## Phase 2: Tests\n- [ ] T2: Add test_hello.py - Write tests\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_specify",
            lambda self, project_path, description, feature_name=None, base_branch=None, project_id=None: SpecifyResult(
                success=True,
                spec_path=str(spec_path),
                spec_number=1,
                feature_name="hello",
                project_path=str(repo),
                base_branch="main",
                spec_root=str(spec_dir),
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_plan",
            lambda self, project_path, spec_path, spec_run_id=None, project_id=None: PlanResult(
                success=True,
                plan_path=str(plan_path),
                spec_run_id=spec_run_id,
                worktree_path=str(repo),
                steps=[{"name": "step-01", "type": "execute"}],
            ),
        )
        monkeypatch.setattr(
            "devgodzilla.services.task_cycle.SpecificationService.run_tasks",
            lambda self, project_path, plan_path, spec_run_id=None, project_id=None: TasksResult(
                success=True,
                tasks_path=str(tasks_path),
                task_count=1,
                parallelizable_count=0,
            ),
        )

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                resp = client.post(
                    f"/projects/{project.id}/brownfield/run",
                    json={
                        "feature_request": "Add a hello endpoint",
                        "output_mode": "protocol",
                    },
                )
                assert resp.status_code in (200, 201, 202), f"Got {resp.status_code}: {resp.text}"
                payload = resp.json()
                assert payload["success"] is True
                assert payload["output_mode"] == "protocol"
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()
