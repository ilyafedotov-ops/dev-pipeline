from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest

from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.models.domain import ProtocolStatus, StepStatus
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService


@dataclass
class _RunScriptCall:
    path: str
    args: Dict[str, Any]


@dataclass
class _CreateFlowCall:
    path: str
    definition: Dict[str, Any]
    summary: Optional[str]
    description: Optional[str]


@dataclass
class _RunFlowCall:
    path: str
    args: Dict[str, Any]


class FakeWindmillClient:
    def __init__(self) -> None:
        self.run_script_calls: List[_RunScriptCall] = []
        self.create_flow_calls: List[_CreateFlowCall] = []
        self.run_flow_calls: List[_RunFlowCall] = []
        self._job_counter = 0

    def _job_id(self) -> str:
        self._job_counter += 1
        return f"job-{self._job_counter}"

    def run_script(self, path: str, args: Optional[Dict[str, Any]] = None) -> str:
        self.run_script_calls.append(_RunScriptCall(path=path, args=args or {}))
        return self._job_id()

    def create_flow(
        self,
        path: str,
        definition: Dict[str, Any],
        *,
        summary: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Any:
        self.create_flow_calls.append(
            _CreateFlowCall(path=path, definition=definition, summary=summary, description=description)
        )
        return {"path": path}

    def run_flow(self, path: str, args: Optional[Dict[str, Any]] = None, **_kwargs: Any) -> str:
        self.run_flow_calls.append(_RunFlowCall(path=path, args=args or {}))
        return self._job_id()


@pytest.fixture
def service_context() -> ServiceContext:
    return ServiceContext(config=Mock())


@pytest.fixture
def devgodzilla_db(tmp_path: Path) -> SQLiteDatabase:
    db_path = tmp_path / "devgodzilla.sqlite"
    db = SQLiteDatabase(db_path)
    db.init_schema()
    return db


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".protocols").mkdir(parents=True, exist_ok=True)
    return repo


def _write_stub_cli(bin_dir: Path, name: str) -> None:
    stub = bin_dir / name
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "cat >/dev/null\n"
        "printf \"ok\\n\"\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def test_orchestrator_dispatches_to_windmill(service_context: ServiceContext, devgodzilla_db: SQLiteDatabase, sample_repo: Path) -> None:
    project = devgodzilla_db.create_project(
        name="demo",
        git_url=str(sample_repo),
        base_branch="main",
        local_path=str(sample_repo),
    )
    protocol_root = sample_repo / ".protocols" / "demo-proto"
    protocol_root.mkdir(parents=True, exist_ok=True)
    run = devgodzilla_db.create_protocol_run(
        project_id=project.id,
        protocol_name="demo-proto",
        status=ProtocolStatus.PENDING,
        base_branch="main",
        worktree_path=str(sample_repo),
        protocol_root=str(protocol_root),
        description="demo",
    )
    step1 = devgodzilla_db.create_step_run(
        protocol_run_id=run.id,
        step_index=0,
        step_name="step-01",
        step_type="execute",
        status=StepStatus.PENDING,
        depends_on=[],
        assigned_agent="opencode",
    )
    step2 = devgodzilla_db.create_step_run(
        protocol_run_id=run.id,
        step_index=1,
        step_name="step-02",
        step_type="execute",
        status=StepStatus.PENDING,
        depends_on=[step1.id],
        assigned_agent=None,
    )

    windmill = FakeWindmillClient()
    orchestrator = OrchestratorService(
        context=service_context,
        db=devgodzilla_db,
        windmill_client=windmill,
        mode=OrchestratorMode.WINDMILL,
    )

    # Start -> planning job in Windmill
    start = orchestrator.start_protocol_run(run.id)
    assert start.success is True
    assert devgodzilla_db.get_protocol_run(run.id).status == ProtocolStatus.PLANNING
    assert windmill.run_script_calls[0].path == "u/devgodzilla/protocol_plan_and_wait"
    assert windmill.run_script_calls[0].args == {"protocol_run_id": run.id}

    # Create flow from steps -> flow created and stored
    flow = orchestrator.create_flow_from_steps(run.id)
    assert flow.success is True
    assert flow.flow_id == f"f/devgodzilla/protocol-{run.id}"
    assert devgodzilla_db.get_protocol_run(run.id).windmill_flow_id == flow.flow_id
    assert windmill.create_flow_calls[0].path == flow.flow_id

    # Ensure flow definition uses expected Windmill scripts
    flow_def = windmill.create_flow_calls[0].definition
    modules = flow_def["modules"]
    assert modules[0]["id"] == str(step1.id)
    assert modules[1]["id"] == str(step2.id)

    exec_module = modules[0]
    assert exec_module["value"]["path"] == "u/devgodzilla/step_execute_api"
    assert exec_module["value"]["input_transforms"]["step_run_id"]["value"] == step1.id

    # Run flow -> running status + Windmill job
    run_flow = orchestrator.run_protocol_flow(run.id)
    assert run_flow.success is True
    assert devgodzilla_db.get_protocol_run(run.id).status == ProtocolStatus.RUNNING
    assert windmill.run_flow_calls[0].path == flow.flow_id
    assert windmill.run_flow_calls[0].args == {"protocol_run_id": run.id}

    # Run a single step via Windmill script (uses assigned_agent defaulting)
    step_job = orchestrator.run_step(step1.id)
    assert step_job.success is True
    assert devgodzilla_db.get_step_run(step1.id).status == StepStatus.RUNNING
    assert windmill.run_script_calls[1].path == "u/devgodzilla/step_execute_api"
    assert windmill.run_script_calls[1].args == {"step_run_id": step1.id}


def test_windmill_worker_entrypoints_plan_and_update_status(
    monkeypatch: pytest.MonkeyPatch,
    service_context: ServiceContext,
    devgodzilla_db: SQLiteDatabase,
    sample_repo: Path,
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _write_stub_cli(bin_dir, "codex")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("DEVGODZILLA_ASSUME_AGENT_AUTH", "true")

    protocol_root = sample_repo / ".protocols" / "demo-proto"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "step-01-setup.md").write_text("# step\n", encoding="utf-8")
    (protocol_root / "step-02-ship.md").write_text("# step\n", encoding="utf-8")

    project = devgodzilla_db.create_project(
        name="demo",
        git_url=str(sample_repo),
        base_branch="main",
        local_path=str(sample_repo),
    )
    run = devgodzilla_db.create_protocol_run(
        project_id=project.id,
        protocol_name="demo-proto",
        status=ProtocolStatus.PENDING,
        base_branch="main",
        worktree_path=str(sample_repo),
        protocol_root=str(protocol_root),
    )

    from devgodzilla.windmill import worker as windmill_worker

    monkeypatch.setattr(windmill_worker, "get_context", lambda: service_context)
    monkeypatch.setattr(windmill_worker, "get_db", lambda: devgodzilla_db)

    planned = windmill_worker.plan_protocol(run.id)
    assert planned["success"] is True
    assert planned["steps_created"] == 2
    assert devgodzilla_db.get_protocol_run(run.id).status == ProtocolStatus.PLANNED

    steps = devgodzilla_db.list_step_runs(run.id)
    assert [s.step_name for s in steps] == ["step-01-setup", "step-02-ship"]

    executed = windmill_worker.execute_step(steps[0].id, agent_id="codex")
    assert executed["success"] is True
    assert devgodzilla_db.get_step_run(steps[0].id).status == StepStatus.COMPLETED

    qa = windmill_worker.run_qa(steps[1].id)
    assert qa["success"] is True
    assert qa["passed"] is True
    assert devgodzilla_db.get_step_run(steps[1].id).status == StepStatus.COMPLETED
