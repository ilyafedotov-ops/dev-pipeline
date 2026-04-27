from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devgodzilla.engines.interface import EngineRequest, EngineResult, SandboxMode
from devgodzilla.engines.opencode import OpenCodeEngine
from devgodzilla.engines.bootstrap import bootstrap_default_engines


def _completed_process(*, args: list[str]) -> Any:
    class _Proc:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

        def __init__(self) -> None:
            self.args = args

    return _Proc()


def test_opencode_engine_invokes_opencode_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_run_cli_command(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        captured["input_text"] = kwargs.get("input_text")
        captured["on_output"] = kwargs.get("on_output")
        captured["tracker_execution_id"] = kwargs.get("tracker_execution_id")
        callback = kwargs.get("on_output")
        if callable(callback):
            callback("stdout", "opencode started\n")
        return EngineResult(
            success=True,
            stdout="ok\n",
            stderr="",
            exit_code=0,
            duration_seconds=0.01,
            metadata={"cmd": cmd[0]},
        )

    monkeypatch.setattr("devgodzilla.engines.opencode.run_cli_command", fake_run_cli_command)

    engine = OpenCodeEngine(default_model="provider/model")
    req = EngineRequest(
        project_id=0,
        protocol_run_id=0,
        step_run_id=1,
        model="provider/model",
        prompt_text="Create a file named hello.txt with content 'ok'.",
        prompt_files=[],
        working_dir=str(tmp_path),
        sandbox=SandboxMode.WORKSPACE_WRITE,
        timeout=10,
        extra={"output_format": "text", "cli_execution_id": "exec-123"},
    )
    result = engine.execute(req)
    assert result.success is True

    cmd = captured.get("cmd")
    assert isinstance(cmd, list)
    assert cmd[:2] == ["opencode", "run"]
    assert "--model" in cmd
    assert "--file" in cmd
    assert captured.get("cwd") == tmp_path
    assert captured.get("input_text") is None
    assert callable(captured.get("on_output"))
    assert captured.get("tracker_execution_id") == "exec-123"


def test_opencode_engine_passes_reasoning_variant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_run_cli_command(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        return EngineResult(
            success=True,
            stdout="ok\n",
            stderr="",
            exit_code=0,
            duration_seconds=0.01,
            metadata={"cmd": cmd[0]},
        )

    monkeypatch.setattr("devgodzilla.engines.opencode.run_cli_command", fake_run_cli_command)

    engine = OpenCodeEngine(default_model="openai/gpt-5-nano")
    req = EngineRequest(
        project_id=0,
        protocol_run_id=0,
        step_run_id=1,
        model="openai/gpt-5-nano",
        prompt_text="Do the thing.",
        prompt_files=[],
        working_dir=str(tmp_path),
        sandbox=SandboxMode.WORKSPACE_WRITE,
        timeout=10,
        extra={"reasoning_effort": "high"},
    )
    result = engine.execute(req)
    assert result.success is True
    cmd = captured["cmd"]
    assert "--variant" in cmd
    assert cmd[cmd.index("--variant") + 1] == "high"


def test_bootstrap_prefers_opencode_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("devgodzilla.engines.opencode.OpenCodeEngine.check_availability", lambda _self: True)
    monkeypatch.setattr("devgodzilla.engines.codex.CodexEngine.check_availability", lambda _self: False)
    monkeypatch.setattr("devgodzilla.engines.claude_code.ClaudeCodeEngine.check_availability", lambda _self: False)

    monkeypatch.setattr("devgodzilla.engines.registry._registry", None)
    bootstrap_default_engines(replace=True)

    from devgodzilla.engines.registry import get_registry

    assert get_registry().get_default().metadata.id == "opencode"
