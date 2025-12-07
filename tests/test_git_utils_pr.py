import os
from pathlib import Path

import httpx
import pytest

from tasksgodzilla.git_utils import create_github_pr, _parse_github_remote
from tasksgodzilla.codex import run_process


def _init_repo(tmp_path: Path, remote: str) -> Path:
    run_process(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True, text=True)
    run_process(["git", "remote", "add", "origin", remote], cwd=tmp_path, capture_output=True, text=True)
    return tmp_path


def test_parse_github_remote_handles_https(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "https://github.com/acme/demo.git")
    assert _parse_github_remote(repo) == ("acme", "demo")


def test_create_github_pr_uses_rest(monkeypatch, tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "https://github.com/acme/demo.git")
    called = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        called["url"] = url
        called["headers"] = headers
        called["json"] = json

        class Resp:
            status_code = 201

        return Resp()

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(httpx, "post", fake_post)

    ok = create_github_pr(repo, head="feature", base="main", title="T", body="B")
    assert ok
    assert "api.github.com/repos/acme/demo/pulls" in called["url"]
    assert called["json"]["head"] == "feature"
    assert called["json"]["base"] == "main"


def test_create_github_pr_requires_token(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path, "https://github.com/acme/demo.git")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert create_github_pr(repo, head="h", base="b", title="t", body="b") is False
