import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

from devgodzilla.services.base import ServiceContext
from devgodzilla.services.git import GitService


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    (path / "src").mkdir(parents=True, exist_ok=True)
    (path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_stage_protocol_changes_excludes_generated_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    (repo / "src" / "app.py").write_text("print('updated')\n", encoding="utf-8")
    (repo / ".specify" / "memory").mkdir(parents=True, exist_ok=True)
    (repo / ".specify" / "memory" / "constitution.md").write_text("# Generated\n", encoding="utf-8")
    (repo / "specs" / "040-feature" / "_runtime").mkdir(parents=True, exist_ok=True)
    (repo / "specs" / "040-feature" / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (repo / "specs" / "040-feature" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (repo / "specs" / "040-feature" / "_runtime" / "README.md").write_text("# Runtime\n", encoding="utf-8")
    (repo / "specs" / "040-feature" / "_runtime" / "step-01-demo.md").write_text("# Step\n", encoding="utf-8")
    (repo / ".devgodzilla" / "steps" / "1" / "artifacts").mkdir(parents=True, exist_ok=True)
    (repo / ".devgodzilla" / "steps" / "1" / "artifacts" / "execution.json").write_text("{}", encoding="utf-8")

    service = GitService(ServiceContext(config=Mock()))
    service._stage_protocol_changes(repo)

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    ).stdout.splitlines()

    assert staged == ["src/app.py"]
