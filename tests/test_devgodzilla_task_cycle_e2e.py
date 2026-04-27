import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

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
def test_task_cycle_helper_agents_run_as_bounded_internal_sidecars_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.api.dependencies import get_db
    from devgodzilla.config import _reset_config_for_tests
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.engines.interface import EngineResult
    from devgodzilla.models.domain import ProtocolStatus, StepStatus
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
        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
            policy_enforcement_mode="warn",
        )
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
        step = db.update_step_run(
            step.id,
            runtime_state={"task_cycle": {"helper_agents": ["trace", "tests", "review"]}},
        )

        helper_prompts: list[str] = []
        owner_prompts: list[str] = []
        active = 0
        max_active = 0
        lock = threading.Lock()

        def _fake_helper_execute(self, *, project_id, protocol_run_id, step_run_id, engine_id, prompt_text, working_dir):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            helper_prompts.append(prompt_text)
            time.sleep(0.05)
            with lock:
                active -= 1
            role = "trace"
            for candidate in ("trace", "tests", "review"):
                if candidate in prompt_text.lower():
                    role = candidate
                    break
            return EngineResult(success=True, stdout=f"{role} findings for owner", stderr="")

        class _FakeEngine:
            metadata = SimpleNamespace(id="opencode", default_model="fake-model")

            def check_availability(self):
                return True

            def execute(self, req):
                owner_prompts.append(req.prompt_text or "")
                return EngineResult(success=True, stdout="owner execution ok", stderr="", exit_code=0, duration_seconds=0.1)

        class _FakeRegistry:
            def get(self, engine_id: str):
                assert engine_id == "opencode"
                return _FakeEngine()

        def _fake_handle_result(self, step_obj, run_obj, engine, engine_result, resolution):
            self.db.update_step_status(
                step_obj.id,
                StepStatus.COMPLETED,
                summary="owner complete",
                model=resolution.model,
                engine_id=resolution.engine_id,
            )
            self.db.update_protocol_status(run_obj.id, ProtocolStatus.RUNNING)
            return ExecutionResult(
                success=True,
                step_run_id=step_obj.id,
                engine_id=resolution.engine_id,
                model=resolution.model,
                stdout=engine_result.stdout,
                stderr=engine_result.stderr,
            )

        monkeypatch.setattr(
            "devgodzilla.services.task_cycle_helpers.TaskCycleHelperRunner.execute_helper_prompt",
            _fake_helper_execute,
        )
        monkeypatch.setattr("devgodzilla.services.execution.get_registry", lambda: _FakeRegistry())
        monkeypatch.setattr("devgodzilla.services.execution.ExecutionService._handle_result", _fake_handle_result)

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:  # type: ignore[arg-type]
                context_resp = client.post(f"/work-items/{step.id}/build-context", json={"refresh": False})
                assert context_resp.status_code == 200, context_resp.text

                implement_resp = client.post(f"/work-items/{step.id}/actions/implement", json={"owner_agent": "dev"})
                assert implement_resp.status_code == 200, implement_resp.text
                payload = implement_resp.json()

                assert payload["status"] == "awaiting_review"
                assert payload["helper_agents"] == ["trace", "tests", "review"]
                assert payload["helper_agent_summary"] == "3 helpers under the owner: 3 completed"
                assert payload["owner_agent"] == "opencode"

                work_item_resp = client.get(f"/work-items/{step.id}")
                assert work_item_resp.status_code == 200
                assert work_item_resp.json()["helper_agent_summary"] == "3 helpers under the owner: 3 completed"

                listed_resp = client.get(f"/projects/{project.id}/task-cycle", params={"protocol_run_id": run.id})
                assert listed_resp.status_code == 200
                listed = listed_resp.json()
                assert len(listed) == 1
                assert listed[0]["id"] == step.id

                helper_summary = (
                    Path(payload["task_dir"]) / "helpers" / "helper_summary.json"
                )
                assert helper_summary.exists()
                helper_payload = json.loads(helper_summary.read_text(encoding="utf-8"))
                assert len(helper_payload["helpers"]) == 3
                assert {item["helper_agent"] for item in helper_payload["helpers"]} == {"trace", "tests", "review"}

                assert len(db.list_step_runs(run.id)) == 1
                assert max_active == 2
                assert len(helper_prompts) == 3
                assert all("Do not edit files, commit code, or create workflow lanes." in prompt for prompt in helper_prompts)
                assert owner_prompts, "owner engine was not invoked"
                assert "# Helper Subtask Findings" in owner_prompts[0]
                assert '"helper_agent": "trace"' in owner_prompts[0]
        finally:
            app.dependency_overrides.clear()
            _reset_config_for_tests()
