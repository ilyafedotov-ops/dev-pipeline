import contextlib
import io
from pathlib import Path

import httpx
import pytest

from deksdenflow.api.app import app
from deksdenflow.config import load_config
from deksdenflow.storage import create_database
from deksdenflow.jobs import create_queue
from deksdenflow.metrics import metrics
from deksdenflow.cli.main import run_cli


@pytest.fixture
def transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.ASGITransport:
    monkeypatch.setenv("DEKSDENFLOW_DB_PATH", str(tmp_path / "cli.sqlite"))
    monkeypatch.setenv("DEKSDENFLOW_REDIS_URL", "fakeredis://")
    monkeypatch.setenv("DEKSDENFLOW_API_BASE", "http://testserver")
    monkeypatch.delenv("DEKSDENFLOW_API_TOKEN", raising=False)
    config = load_config()
    db = create_database(db_path=config.db_path, db_url=config.db_url)
    db.init_schema()
    queue = create_queue(config.redis_url)
    app.state.config = config  # type: ignore[attr-defined]
    app.state.db = db  # type: ignore[attr-defined]
    app.state.queue = queue  # type: ignore[attr-defined]
    app.state.metrics = metrics  # type: ignore[attr-defined]
    return httpx.ASGITransport(app=app)


def run_cmd(argv, transport: httpx.ASGITransport):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(argv, transport=transport)
    return code, buf.getvalue()


def test_cli_project_and_protocol_flow(transport: httpx.ASGITransport) -> None:
    code, out = run_cmd(
        ["projects", "create", "--name", "demo", "--git-url", "/tmp/demo.git", "--base-branch", "main"],
        transport,
    )
    assert code == 0
    assert "Created project" in out

    code, out = run_cmd(["projects", "list"], transport)
    assert code == 0
    assert "demo" in out

    code, out = run_cmd(
        ["protocols", "create-and-start", "--project", "1", "--name", "0001-demo", "--base-branch", "main"],
        transport,
    )
    assert code == 0
    assert "planning enqueued" in out

    code, out = run_cmd(["protocols", "list", "--project", "1"], transport)
    assert code == 0
    assert "0001-demo" in out

    code, out = run_cmd(["events", "recent", "--project", "1", "--limit", "5"], transport)
    assert code == 0

    code, out = run_cmd(["queues", "stats"], transport)
    assert code == 0
    assert "backend" in out
