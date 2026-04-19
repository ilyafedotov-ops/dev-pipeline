from __future__ import annotations

import logging
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from devgodzilla.api import schemas
from devgodzilla.api.routes import agents as agents_routes
from devgodzilla.api.routes import clarifications as clarifications_routes
from devgodzilla.api.routes.quality import get_quality_dashboard
from devgodzilla.api.routes.runs import get_run_logs
from devgodzilla.api.routes.sprints import get_sprint_metrics
from devgodzilla.api.routes.tasks import create_task, list_tasks
from devgodzilla.api.routes.templates import list_templates
from devgodzilla.api.routes.windmill import list_flows
from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.services.template_manager import Template


@contextmanager
def temp_db_context():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        yield db, Path(tmpdir)


def _create_project(db: SQLiteDatabase) -> int:
    project = db.create_project(
        name="logging-project",
        git_url="https://github.com/example/logging-project.git",
        base_branch="main",
        local_path="/tmp/logging-project",
    )
    return project.id


def test_task_routes_emit_structured_logs(caplog) -> None:
    with temp_db_context() as (db, _tmpdir):
        project_id = _create_project(db)
        caplog.set_level(logging.INFO)

        created = create_task(
            schemas.AgileTaskCreate(
                project_id=project_id,
                title="Instrument logging",
                task_type="task",
                priority="high",
                board_status="todo",
                labels=["logging"],
            ),
            db=db,
        )
        tasks = list_tasks(project_id=project_id, db=db)

    created_record = next(record for record in caplog.records if record.message == "task_created")
    listed_record = next(record for record in caplog.records if record.message == "tasks_listed")

    assert created_record.project_id == project_id
    assert created_record.task_id == created.id
    assert created_record.board_status == "todo"
    assert listed_record.project_id == project_id
    assert listed_record.result_count == len(tasks) == 1


def test_sprint_metrics_emit_summary_log(caplog) -> None:
    with temp_db_context() as (db, _tmpdir):
        project_id = _create_project(db)
        sprint = db.create_sprint(project_id=project_id, name="Sprint 1", status="active")
        db.create_task(project_id=project_id, sprint_id=sprint.id, title="Done", board_status="done", story_points=3)
        db.create_task(project_id=project_id, sprint_id=sprint.id, title="Todo", board_status="todo", story_points=5)

        caplog.set_level(logging.INFO)
        metrics = get_sprint_metrics(sprint.id, db=db)

    record = next(record for record in caplog.records if record.message == "sprint_metrics_computed")

    assert metrics.total_tasks == 2
    assert metrics.completed_tasks == 1
    assert record.project_id == project_id
    assert record.sprint_id == sprint.id
    assert record.total_tasks == 2
    assert record.completed_points == 3


def test_quality_dashboard_emits_aggregate_log(caplog) -> None:
    with temp_db_context() as (db, _tmpdir):
        project_id = _create_project(db)
        protocol = db.create_protocol_run(
            project_id=project_id,
            protocol_name="logging-protocol",
            status="running",
            base_branch="main",
        )
        step = db.create_step_run(
            protocol_run_id=protocol.id,
            step_index=0,
            step_name="qa",
            step_type="qa",
            status="completed",
        )
        db.create_qa_result(
            project_id=project_id,
            protocol_run_id=protocol.id,
            step_run_id=step.id,
            verdict="warn",
            gate_results=[],
            findings=[
                {
                    "severity": "warning",
                    "message": "Missing assertion",
                    "metadata": {"article": "2", "article_title": "Quality"},
                }
            ],
        )

        caplog.set_level(logging.INFO)
        dashboard = get_quality_dashboard(db=db, ctx=SimpleNamespace(request_id="req-quality-1"))

    record = next(record for record in caplog.records if record.message == "quality_dashboard_loaded")

    assert dashboard.overview.total_protocols == 1
    assert dashboard.overview.warnings == 1
    assert record.request_id == "req-quality-1"
    assert record.total_protocols == 1
    assert record.recent_findings_count == 1


def test_run_logs_emit_loaded_log(caplog) -> None:
    with temp_db_context() as (db, tmpdir):
        project_id = _create_project(db)
        log_path = tmpdir / "worker.log"
        log_path.write_text("line one\nline two\n", encoding="utf-8")
        db.create_job_run(
            run_id="run-log-1",
            job_type="execute_step",
            status="completed",
            project_id=project_id,
            log_path=str(log_path),
        )

        caplog.set_level(logging.INFO)
        artifact = get_run_logs("run-log-1", db=db)

    record = next(record for record in caplog.records if record.message == "run_logs_loaded")

    assert "line one" in artifact.content
    assert record.run_id == "run-log-1"
    assert record.log_path == str(log_path)
    assert record.truncated is False


def test_agents_list_emits_source_and_count_log(caplog, monkeypatch) -> None:
    class FakeAgentConfigService:
        def __init__(self, ctx, db=None):
            self.ctx = ctx

        def list_agents(self, enabled_only=False, project_id=None):
            return [
                SimpleNamespace(
                    id="codex",
                    name="Codex",
                    kind="cli",
                    capabilities=["execute"],
                    enabled=True,
                    default_model="o4-mini",
                    command_dir=None,
                    command="codex",
                    endpoint=None,
                    sandbox="workspace-write",
                    format="default",
                    timeout_seconds=30,
                    max_retries=1,
                )
            ]

    monkeypatch.setattr(agents_routes, "AgentConfigService", FakeAgentConfigService)

    caplog.set_level(logging.INFO)
    result = agents_routes.list_agents(
        project_id=None,
        enabled_only=False,
        ctx=SimpleNamespace(request_id="req-agents-1"),
        db=None,
    )

    record = next(record for record in caplog.records if record.message == "agents_listed")

    assert len(result) == 1
    assert record.request_id == "req-agents-1"
    assert record.source == "config"
    assert record.result_count == 1


def test_clarification_answer_emits_structured_log(caplog) -> None:
    clarification = SimpleNamespace(scope="protocol", key="policy.mode")
    updated = SimpleNamespace(project_id=17, protocol_run_id=23)

    class FakeDB:
        def get_clarification_by_id(self, clarification_id):
            assert clarification_id == 5
            return clarification

        def answer_clarification(self, **kwargs):
            assert kwargs["scope"] == "protocol"
            assert kwargs["key"] == "policy.mode"
            return updated

    caplog.set_level(logging.INFO)
    response = clarifications_routes.answer_clarification(
        5,
        schemas.ClarificationAnswer(answer="Use blocking mode", answered_by="ilya"),
        db=FakeDB(),
    )

    record = next(record for record in caplog.records if record.message == "clarification_answered")

    assert response is updated
    assert record.project_id == 17
    assert record.protocol_run_id == 23
    assert record.clarification_id == 5
    assert record.answered_by == "ilya"


def test_templates_list_emits_structured_log(caplog) -> None:
    manager = SimpleNamespace(
        list_templates=lambda category=None: [
            Template(
                id="spec-1",
                name="Spec Template",
                description="Spec description",
                category="specification",
                content="hello",
            )
        ]
    )

    caplog.set_level(logging.INFO)
    result = list_templates(category="specification", search=None, manager=manager)

    record = next(record for record in caplog.records if record.message == "templates_listed")

    assert result.total == 1
    assert record.category == "specification"
    assert record.result_count == 1
    assert record.category_count == 1


def test_windmill_flows_list_emits_structured_log(caplog) -> None:
    windmill = SimpleNamespace(
        list_flows=lambda prefix=None: [
            SimpleNamespace(path="f/devgodzilla/test", name="Test Flow", summary="summary")
        ]
    )

    caplog.set_level(logging.INFO)
    result = list_flows(prefix="f/devgodzilla", windmill=windmill)

    record = next(record for record in caplog.records if record.message == "windmill_flows_listed")

    assert len(result) == 1
    assert record.prefix == "f/devgodzilla"
    assert record.result_count == 1
