import tempfile
from pathlib import Path
from unittest import mock

from deksdenflow import ci


def test_trigger_ci_github_runs_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        captured = {}

        def fake_run(cmd, cwd=None, capture_output=False, text=True, input_text=None, check=True):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["capture_output"] = capture_output
            captured["text"] = text
            captured["input_text"] = input_text
            captured["check"] = check
            return mock.Mock()

        with mock.patch.object(ci.shutil, "which", return_value="/usr/bin/gh"), \
            mock.patch.object(ci, "run_process", side_effect=fake_run):
            result = ci.trigger_ci("github", repo_root, "1234-demo")

        assert result is True
        assert captured["cmd"][:4] == ["gh", "workflow", "run", "--ref"]
        assert captured["cmd"][-1] == "1234-demo"
        assert captured["cwd"] == repo_root


def test_trigger_ci_missing_cli_returns_false():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        with mock.patch.object(ci.shutil, "which", return_value=None):
            result = ci.trigger_ci("gitlab", repo_root, "1234-demo")
        assert result is False
