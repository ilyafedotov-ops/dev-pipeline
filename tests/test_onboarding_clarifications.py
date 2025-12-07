import os
import subprocess
from pathlib import Path

from deksdenflow.domain import ProtocolStatus
from deksdenflow.storage import Database
from deksdenflow.workers import onboarding_worker


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True)
    (path / "README.md").write_text("demo", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, env={**os.environ, "GIT_AUTHOR_NAME": "tester", "GIT_AUTHOR_EMAIL": "tester@example.com", "GIT_COMMITTER_NAME": "tester", "GIT_COMMITTER_EMAIL": "tester@example.com"})


def test_onboarding_emits_clarifications_without_block(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.setenv("DEKSDENFLOW_AUTO_CLONE", "false")
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()
    project = db.create_project("demo", str(repo), "main", "github", {"planning": "gpt-5.1-high"})
    run = db.create_protocol_run(project.id, "setup-test", ProtocolStatus.PENDING, "main", None, None, "setup")

    onboarding_worker.handle_project_setup(project.id, db, protocol_run_id=run.id)

    run_after = db.get_protocol_run(run.id)
    assert run_after.status == ProtocolStatus.COMPLETED
    events = db.list_events(run.id)
    clar = [e for e in events if e.event_type == "setup_clarifications"]
    assert clar, "expected clarifications event"
    assert clar[0].metadata.get("blocking") is False


def test_onboarding_clarifications_can_block(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.setenv("DEKSDENFLOW_AUTO_CLONE", "false")
    monkeypatch.setenv("DEKSDENFLOW_REQUIRE_ONBOARDING_CLARIFICATIONS", "true")
    db = Database(tmp_path / "db2.sqlite")
    db.init_schema()
    project = db.create_project("demo", str(repo), "main", "github", None)
    run = db.create_protocol_run(project.id, "setup-test2", ProtocolStatus.PENDING, "main", None, None, "setup")

    onboarding_worker.handle_project_setup(project.id, db, protocol_run_id=run.id)

    run_after = db.get_protocol_run(run.id)
    assert run_after.status == ProtocolStatus.BLOCKED
    events = db.list_events(run.id)
    blocked = [e for e in events if e.event_type == "setup_blocked"]
    assert blocked, "expected blocked event for clarifications"
