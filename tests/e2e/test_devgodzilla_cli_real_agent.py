from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(*args: str, cwd: Path, env: dict[str, str], timeout: int = 60) -> dict:
    cmd = [sys.executable, "-m", "devgodzilla.cli.main", *args]
    proc = subprocess.run(  # noqa: S603
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "CLI command failed\n"
            f"cmd: {cmd}\n"
            f"cwd: {cwd}\n"
            f"exit_code: {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}\n"
        )
    return json.loads(proc.stdout)


@pytest.mark.integration
def test_cli_real_agent_discovery_and_protocol_generation(tmp_path: Path) -> None:
    if os.environ.get("DEVGODZILLA_RUN_E2E_REAL_AGENT") != "1":
        pytest.skip("Set DEVGODZILLA_RUN_E2E_REAL_AGENT=1 to enable real-agent E2E.")
    if shutil.which("git") is None:
        pytest.skip("git is required for this E2E test.")
    if shutil.which("opencode") is None:
        pytest.skip("opencode is required for this E2E test.")

    repo_root = Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(repo_root),
            "DEVGODZILLA_ENV": "test",
            "DEVGODZILLA_DB_PATH": str(tmp_path / "devgodzilla.sqlite"),
            "DEVGODZILLA_DEFAULT_ENGINE_ID": "opencode",
            "DEVGODZILLA_OPENCODE_MODEL": "zai-coding-plan/glm-4.6",
        }
    )

    git_url = "https://github.com/ilyafedotov-ops/click"
    cloned_repo = tmp_path / "click"
    subprocess.run(  # noqa: S603
        ["git", "clone", "--depth", "1", git_url, str(cloned_repo)],
        cwd=tmp_path,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    base_branch = (
        subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cloned_repo, env=env, text=True)  # noqa: S603,S607
        .strip()
    )

    created = _run_cli(
        "--json",
        "project",
        "create",
        "click-e2e-real-agent",
        "--repo",
        git_url,
        "--branch",
        base_branch,
        "--local-path",
        str(cloned_repo),
        cwd=tmp_path,
        env=env,
    )
    assert created["success"] is True
    project_id = int(created["project_id"])

    discovery = _run_cli(
        "--json",
        "project",
        "discover",
        str(project_id),
        "--agent",
        "--pipeline",
        "--engine",
        "opencode",
        "--model",
        "zai-coding-plan/glm-4.6",
        cwd=tmp_path,
        env=env,
        timeout=600,  # Real agent discovery takes ~2-5 min
    )
    assert discovery["success"] is True
    assert discovery["engine_id"] == "opencode"
    assert discovery["model"] == "zai-coding-plan/glm-4.6"

    tasksgodzilla_dir = cloned_repo / "tasksgodzilla"
    assert (tasksgodzilla_dir / "DISCOVERY.md").exists()
    summary_path = tasksgodzilla_dir / "DISCOVERY_SUMMARY.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert isinstance(summary, dict)
    assert "languages" in summary

    proto = _run_cli(
        "--json",
        "protocol",
        "create",
        str(project_id),
        "e2e-real-agent-protocol",
        "--description",
        "E2E: generate protocol artifacts via opencode",
        "--branch",
        base_branch,
        cwd=tmp_path,
        env=env,
    )
    protocol_run_id = int(proto["protocol_run_id"])

    worktree = _run_cli("--json", "protocol", "worktree", str(protocol_run_id), cwd=tmp_path, env=env)
    assert Path(worktree["worktree_path"]).exists()

    generated = _run_cli(
        "--json",
        "protocol",
        "generate",
        str(protocol_run_id),
        "--steps",
        "2",
        "--engine",
        "opencode",
        "--model",
        "zai-coding-plan/glm-4.6",
        cwd=tmp_path,
        env=env,
        timeout=300,  # Real agent protocol generation takes ~1-3 min
    )
    assert generated["success"] is True
    assert generated["engine_id"] == "opencode"
    assert generated["model"] == "zai-coding-plan/glm-4.6"
    protocol_root = Path(generated["protocol_root"])
    assert (protocol_root / "plan.md").exists()
    assert len(list(protocol_root.glob("step-*.md"))) >= 2

