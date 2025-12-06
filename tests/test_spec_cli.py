import json
from pathlib import Path

from deksdenflow.cli.main import run_cli
from deksdenflow.spec import PROTOCOL_SPEC_KEY
from deksdenflow.domain import ProtocolStatus
from deksdenflow.storage import Database


def _make_codex_workspace(root: Path, name: str) -> Path:
    workspace = root / "codex"
    protocol_root = workspace / ".protocols" / name
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-step.md").write_text("step content", encoding="utf-8")
    return workspace


def _make_codemachine_workspace(root: Path) -> Path:
    workspace = root / "codemachine"
    config_dir = workspace / ".codemachine" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (workspace / ".codemachine" / "outputs").mkdir(parents=True, exist_ok=True)
    (workspace / ".codemachine" / "prompts").mkdir(parents=True, exist_ok=True)
    (workspace / ".codemachine" / "prompts" / "build.md").write_text("build prompt", encoding="utf-8")
    (workspace / ".codemachine" / "prompts" / "plan.md").write_text("plan prompt", encoding="utf-8")
    (config_dir / "main.agents.js").write_text(
        """
        export default [
          { "id": "plan", "promptPath": "prompts/plan.md", "moduleId": "loop-check" },
          { "id": "build", "promptPath": "prompts/build.md" }
        ];
        """,
        encoding="utf-8",
    )
    (config_dir / "modules.js").write_text(
        """
        export default [
          { "id": "loop-check", "behavior": { "type": "loop", "action": "stepBack", "maxIterations": 2 } },
          { "id": "handoff", "behavior": { "type": "trigger", "triggerAgentId": "build", "targetAgentId": "build" } }
        ];
        """,
        encoding="utf-8",
    )
    (workspace / ".codemachine" / "template.json").write_text('{"template":"spec-mixed","version":"0.0.1"}', encoding="utf-8")
    return workspace


def test_spec_cli_reports_hashes_for_mixed_runs(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "cli.sqlite"
    monkeypatch.setenv("DEKSDENFLOW_DB_PATH", str(db_path))
    monkeypatch.delenv("DEKSDENFLOW_DB_URL", raising=False)
    monkeypatch.delenv("DEKSDENFLOW_API_TOKEN", raising=False)

    db = Database(db_path)
    db.init_schema()

    codex_workspace = _make_codex_workspace(tmp_path, "0001-mixed")
    codex_project = db.create_project("codex", str(codex_workspace), "main", None, None)
    db.create_protocol_run(
        codex_project.id,
        "0001-mixed",
        ProtocolStatus.PLANNED,
        "main",
        str(codex_workspace),
        str(codex_workspace / ".protocols" / "0001-mixed"),
        "codex run",
    )

    cm_workspace = _make_codemachine_workspace(tmp_path)
    cm_project = db.create_project("cm", str(cm_workspace), "main", None, None)
    cm_run = db.create_protocol_run(
        cm_project.id,
        "0002-mixed",
        ProtocolStatus.PLANNED,
        "main",
        str(cm_workspace),
        str(cm_workspace / ".codemachine"),
        "cm run",
    )

    from io import StringIO
    import contextlib

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["--json", "spec", "validate", "--backfill-missing"], transport=None)
    assert code == 0
    results = json.loads(buf.getvalue())
    by_name = {r["protocol_name"]: r for r in results}
    assert set(by_name.keys()) == {"0001-mixed", "0002-mixed"}
    for res in by_name.values():
        assert res["backfilled"] is True
        assert res["errors"] == []
        assert res["spec_hash"]

    # Inspect backfilled specs for QA and policy coverage.
    cm_after = db.get_protocol_run(cm_run.id)
    cm_spec = (cm_after.template_config or {}).get(PROTOCOL_SPEC_KEY)
    assert cm_spec
    policies_all = [p for step in cm_spec["steps"] for p in step.get("policies", [])]
    assert policies_all  # loop/trigger policies present
    assert any(p.get("behavior") == "trigger" for p in policies_all)
    codex_after = db.get_protocol_run(1)
    codex_spec = (codex_after.template_config or {}).get(PROTOCOL_SPEC_KEY)
    assert codex_spec
    qa_cfg = codex_spec["steps"][0]["qa"]
    assert qa_cfg
    assert "prompt" in qa_cfg
