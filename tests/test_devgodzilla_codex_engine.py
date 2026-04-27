from __future__ import annotations

from pathlib import Path
from typing import Any

from devgodzilla.engines.codex import CodexEngine
from devgodzilla.engines.interface import EngineRequest, EngineResult, SandboxMode


def test_codex_engine_passes_reasoning_effort(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_run_cli_command(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        captured["input_text"] = kwargs.get("input_text")
        return EngineResult(
            success=True,
            stdout="ok\n",
            stderr="",
            exit_code=0,
            duration_seconds=0.01,
            metadata={"cmd": cmd[0]},
        )

    monkeypatch.setattr("devgodzilla.engines.cli_adapter.run_cli_command", fake_run_cli_command)

    engine = CodexEngine(default_model="gpt-5.4")
    req = EngineRequest(
        project_id=0,
        protocol_run_id=0,
        step_run_id=1,
        model="gpt-5.4",
        prompt_text="Say ok",
        working_dir=str(tmp_path),
        sandbox=SandboxMode.WORKSPACE_WRITE,
        timeout=10,
        extra={"reasoning_effort": "high"},
    )
    result = engine.execute(req)

    assert result.success is True
    cmd = captured["cmd"]
    assert cmd[:2] == ["codex", "exec"]
    assert "-c" in cmd
    assert 'model_reasoning_effort="high"' in cmd
    assert captured["cwd"] == tmp_path
    assert captured["input_text"] == "Say ok"
