import os
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from tasksgodzilla.api.app import app
except ImportError:  # pragma: no cover - fastapi optional
    TestClient = None  # type: ignore
    app = None  # type: ignore


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_codemachine_import_inline_creates_steps_and_template() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "api-test.sqlite"
        os.environ["TASKSGODZILLA_DB_PATH"] = str(db_path)
        os.environ.pop("TASKSGODZILLA_API_TOKEN", None)
        os.environ["TASKSGODZILLA_REDIS_URL"] = "fakeredis://"

        workspace = Path(tmpdir) / "workspace"
        config_dir = workspace / ".codemachine" / "config"
        _write(
            config_dir / "main.agents.js",
            """
            export default [
              { "id": "plan", "promptPath": "prompts/plan.md", "engineId": "codex", "model": "gpt-5.1-high", "moduleId": "iteration-checker" },
              { "id": "build", "promptPath": "prompts/build.md", "engineId": "codex" }
            ];
            """,
        )
        _write(
            config_dir / "modules.js",
            """
            export default [
              { "id": "iteration-checker", "behavior": { "type": "loop", "action": "stepBack", "maxIterations": 2, "stepBack": 1 } }
            ];
            """,
        )
        _write(workspace / ".codemachine" / "template.json", '{"template":"spec-to-code","version":"0.0.1"}')
        (workspace / ".codemachine" / "outputs").mkdir(parents=True, exist_ok=True)
        _write(workspace / ".codemachine" / "prompts" / "plan.md", "plan prompt")
        _write(workspace / ".codemachine" / "prompts" / "build.md", "build prompt")

        with TestClient(app) as client:  # type: ignore[arg-type]
            proj = client.post(
                "/projects",
                json={
                    "name": "demo",
                    "git_url": str(workspace),
                    "base_branch": "main",
                },
            ).json()

            resp = client.post(
                f"/projects/{proj['id']}/codemachine/import",
                json={
                    "protocol_name": "9999-demo",
                    "workspace_path": str(workspace),
                    "enqueue": False,
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            run = body["protocol_run"]
            assert run["template_config"]["template"]["template"] == "spec-to-code"

            steps = client.get(f"/protocols/{run['id']}/steps").json()
            assert len(steps) == 2
            assert steps[0]["engine_id"] == "codex"
            assert steps[0]["policy"][0]["behavior"] == "loop"
