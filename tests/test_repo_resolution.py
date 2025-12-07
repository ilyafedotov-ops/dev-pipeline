import os
import subprocess
from pathlib import Path

import pytest

from tasksgodzilla import project_setup


def _init_origin_repo(origin: Path) -> None:
    origin.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(origin)], check=True)
    (origin / "README.md").write_text("hello", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "tester",
        "GIT_AUTHOR_EMAIL": "tester@example.com",
        "GIT_COMMITTER_NAME": "tester",
        "GIT_COMMITTER_EMAIL": "tester@example.com",
    }
    subprocess.run(["git", "-C", str(origin), "add", "README.md"], check=True, env=env)
    subprocess.run(["git", "-C", str(origin), "commit", "-m", "init"], check=True, env=env)


def test_ensure_local_repo_clones_when_missing(tmp_path) -> None:
    origin = tmp_path / "origin"
    _init_origin_repo(origin)
    projects_root = tmp_path / "Projects"
    git_url = origin.as_uri()

    repo_path = project_setup.ensure_local_repo(git_url, "demo", projects_root=projects_root, clone_if_missing=True)

    assert repo_path.exists()
    assert repo_path.parent == projects_root
    assert (repo_path / ".git").exists()
    assert repo_path.name == "origin"


def test_ensure_local_repo_respects_auto_clone_flag(tmp_path, monkeypatch) -> None:
    projects_root = tmp_path / "Projects"
    monkeypatch.setenv("TASKSGODZILLA_AUTO_CLONE", "false")
    with pytest.raises(FileNotFoundError):
        project_setup.ensure_local_repo("https://example.com/repo.git", "demo", projects_root=projects_root, clone_if_missing=None)


def test_configure_git_remote_prefers_github_ssh(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/example/demo.git"], cwd=repo_root, check=True)
    monkeypatch.setenv("TASKSGODZILLA_GH_SSH", "true")

    origin = project_setup.configure_git_remote(repo_root, "https://github.com/example/demo.git", prefer_ssh_remote=True)

    assert origin == "git@github.com:example/demo.git"
    out = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_root, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "git@github.com:example/demo.git"
