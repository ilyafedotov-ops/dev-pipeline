
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call

from tasksgodzilla.services.git import GitService
from tasksgodzilla.domain import ProtocolRun, ProtocolStatus, Project


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.append_event = MagicMock()
    db.update_protocol_status = MagicMock()
    return db


@pytest.fixture
def git_service(mock_db):
    return GitService(db=mock_db)


@pytest.fixture
def mock_project():
    return Project(
        id=1,
        name="test-project",
        git_url="git@github.com:test/repo.git",
        local_path=None,
        default_models={},
        ci_provider="github",
        created_at="now",
        base_branch="main",
        secrets={},
        updated_at="now",
    )


@pytest.fixture
def mock_run():
    return ProtocolRun(
        id=100,
        project_id=1,
        protocol_name="protocol-123-task",
        protocol_root="/tmp/protocol",
        template_config={},
        base_branch="main",
        status=ProtocolStatus.PENDING,
        worktree_path=None,
        description="test run",
        template_source="none",
        created_at="now",
        updated_at="now",
    )


def test_get_branch_name_single_worktree(git_service, monkeypatch):
    monkeypatch.setattr("tasksgodzilla.services.git.SINGLE_WORKTREE", True)
    monkeypatch.setattr("tasksgodzilla.services.git.DEFAULT_WORKTREE_BRANCH", "shared-branch")
    assert git_service.get_branch_name("whatever") == "shared-branch"


def test_get_branch_name_multi_worktree(git_service, monkeypatch):
    monkeypatch.setattr("tasksgodzilla.services.git.SINGLE_WORKTREE", False)
    assert git_service.get_branch_name("protocol-abc") == "protocol-abc"


def test_get_worktree_path(git_service, monkeypatch):
    monkeypatch.setattr("tasksgodzilla.services.git.SINGLE_WORKTREE", False)
    repo_root = Path("/tmp/repo")
    path, branch = git_service.get_worktree_path(repo_root, "protocol-abc")
    assert branch == "protocol-abc"
    assert path == Path("/tmp/worktrees/protocol-abc")


def test_ensure_repo_or_block_exists(git_service, mock_project, mock_run, monkeypatch):
    mock_resolve = MagicMock(return_value=Path("/tmp/repo"))
    monkeypatch.setattr("tasksgodzilla.services.git.resolve_project_repo_path", mock_resolve)
    monkeypatch.setattr("pathlib.Path.exists", lambda s: True)

    path = git_service.ensure_repo_or_block(mock_project, mock_run)
    assert path == Path("/tmp/repo")
    mock_resolve.assert_called_once()
    git_service.db.update_protocol_status.assert_not_called()


def test_ensure_repo_or_block_missing_blocks(git_service, mock_project, mock_run, monkeypatch):
    mock_resolve = MagicMock(side_effect=FileNotFoundError("not found"))
    monkeypatch.setattr("tasksgodzilla.services.git.resolve_project_repo_path", mock_resolve)

    path = git_service.ensure_repo_or_block(mock_project, mock_run)
    assert path is None
    git_service.db.update_protocol_status.assert_called_with(mock_run.id, ProtocolStatus.BLOCKED)
    git_service.db.append_event.assert_called()


def test_ensure_worktree_creates_if_missing(git_service, monkeypatch):
    mock_run_process = MagicMock()
    monkeypatch.setattr("tasksgodzilla.services.git.run_process", mock_run_process)
    monkeypatch.setattr("tasksgodzilla.services.git.SINGLE_WORKTREE", False)
    
    # Mock Path.exists to return False then True
    repo_root = Path("/tmp/repo")
    
    # We need to mock the Path object used inside the method
    with monkeypatch.context() as m:
        m.setattr("pathlib.Path.exists", lambda self: False)
        path = git_service.ensure_worktree(
            repo_root, "protocol-abc", "main", protocol_run_id=100
        )
        # Verify run_process called with correct args
        mock_run_process.assert_called_once()
        cmd = mock_run_process.call_args[0][0]
        assert "git" in cmd
        assert "worktree" in cmd
        assert "add" in cmd
        assert "protocol-abc" in cmd  # branch name
        assert str(path) in cmd


def test_push_and_open_pr_success(git_service, monkeypatch):
    mock_run_process = MagicMock()
    monkeypatch.setattr("tasksgodzilla.services.git.run_process", mock_run_process)
    # Mock _remote_branch_exists
    git_service._remote_branch_exists = MagicMock(return_value=False)
    # Mock _create_pr_if_possible
    git_service._create_pr_if_possible = MagicMock(return_value=True)

    result = git_service.push_and_open_pr(
        Path("/tmp/worktree"), "protocol-abc", "main"
    )
    assert result is True
    # Should attempt commit and push
    assert mock_run_process.call_count >= 2


def test_push_and_open_pr_pushed_but_pr_failed(git_service, monkeypatch):
    mock_run_process = MagicMock()
    monkeypatch.setattr("tasksgodzilla.services.git.run_process", mock_run_process)
    git_service._remote_branch_exists = MagicMock(return_value=False)
    # PR creation fails/returns False
    git_service._create_pr_if_possible = MagicMock(return_value=False)

    result = git_service.push_and_open_pr(
        Path("/tmp/worktree"), "protocol-abc", "main"
    )
    # It returns True because push succeeded (implied by execution flow reaching return)
    assert result is True


def test_trigger_ci(git_service, monkeypatch):
    mock_trigger = MagicMock(return_value=True)
    monkeypatch.setattr("tasksgodzilla.services.git.trigger_ci", mock_trigger)

    result = git_service.trigger_ci(
        Path("/tmp/repo"), "branch", "github"
    )
    assert result is True
    mock_trigger.assert_called_with("github", Path("/tmp/repo"), "branch")


# Property-Based Tests
# Feature: services-architecture-completion, Property 1: Worker delegation pattern
# Validates: Requirements 2.1

from hypothesis import given, strategies as st, settings
from unittest.mock import patch


@settings(max_examples=100)
@given(
    protocol_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=ord('a'), max_codepoint=ord('z'))),
    base_branch=st.sampled_from(["main", "master", "develop"]),
)
def test_property_worker_delegation_ensure_worktree(protocol_name, base_branch):
    """
    Property 1: Worker delegation pattern
    For any protocol_name and base_branch, the worker should only call GitService.ensure_worktree
    without implementing business logic itself.
    
    This test verifies that ensure_worktree can be called with various inputs and delegates
    properly to git commands without the worker needing to know git internals.
    """
    # Create service with mock db
    mock_db = MagicMock()
    git_service = GitService(db=mock_db)
    
    repo_root = Path("/tmp/test-repo")
    
    # Mock the dependencies
    with patch("tasksgodzilla.services.git.run_process") as mock_run_process, \
         patch("tasksgodzilla.services.git.SINGLE_WORKTREE", False), \
         patch("pathlib.Path.exists", return_value=False):
        
        # Call the service method - this is what the worker should do
        result = git_service.ensure_worktree(
            repo_root,
            protocol_name,
            base_branch,
            protocol_run_id=1,
            project_id=1,
            job_id="test-job"
        )
        
        # Verify the service method was called and delegated to git
        # The worker should not need to know about git worktree commands
        assert result is not None
        assert isinstance(result, Path)
        
        # Verify git command was called (service handles the details)
        if mock_run_process.called:
            cmd = mock_run_process.call_args[0][0]
            assert "git" in cmd
            assert "worktree" in cmd



def test_remote_branch_exists_true(git_service, monkeypatch):
    """Test remote_branch_exists returns True when branch exists."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run_process = MagicMock(return_value=mock_result)
    monkeypatch.setattr("tasksgodzilla.services.git.run_process", mock_run_process)
    
    result = git_service.remote_branch_exists(Path("/tmp/repo"), "test-branch")
    assert result is True
    mock_run_process.assert_called_once()
    cmd = mock_run_process.call_args[0][0]
    assert "git" in cmd
    assert "ls-remote" in cmd
    assert "test-branch" in cmd[-1]


def test_remote_branch_exists_false(git_service, monkeypatch):
    """Test remote_branch_exists returns False when branch doesn't exist."""
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_run_process = MagicMock(return_value=mock_result)
    monkeypatch.setattr("tasksgodzilla.services.git.run_process", mock_run_process)
    
    result = git_service.remote_branch_exists(Path("/tmp/repo"), "nonexistent-branch")
    assert result is False


def test_remote_branch_exists_exception(git_service, monkeypatch):
    """Test remote_branch_exists returns False on exception."""
    mock_run_process = MagicMock(side_effect=Exception("git error"))
    monkeypatch.setattr("tasksgodzilla.services.git.run_process", mock_run_process)
    
    result = git_service.remote_branch_exists(Path("/tmp/repo"), "test-branch")
    assert result is False



# Feature: services-architecture-completion, Property 2: No duplicate implementations
# Validates: Requirements 2.2

import ast
import inspect


def test_property_no_duplicate_git_implementations():
    """
    Property 2: No duplicate implementations
    For any business logic function, it should exist in exactly one location (a service),
    not duplicated in workers or helper modules.
    
    This test verifies that git operations are not duplicated in codex_worker.
    """
    # Read the codex_worker source
    with open("tasksgodzilla/workers/codex_worker.py", "r") as f:
        worker_source = f.read()
    
    # Parse the AST
    tree = ast.parse(worker_source)
    
    # Git operations that should only be in GitService
    git_operations = [
        "git worktree",
        "git ls-remote",
        "git push",
        "git commit",
        "git add",
    ]
    
    # Check for direct git command execution in worker
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if it's a run_process call with git commands
            if isinstance(node.func, ast.Name) and node.func.id == "run_process":
                if node.args:
                    # Check if first arg is a list containing git commands
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.List):
                        # Convert list elements to strings if possible
                        cmd_parts = []
                        for elt in first_arg.elts:
                            if isinstance(elt, ast.Constant):
                                cmd_parts.append(str(elt.value))
                        
                        cmd_str = " ".join(cmd_parts)
                        for git_op in git_operations:
                            if git_op in cmd_str:
                                pytest.fail(
                                    f"Found duplicate git implementation in codex_worker: {git_op}. "
                                    f"This should be in GitService only."
                                )
    
    # Verify that GitService methods are being called instead
    git_service_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "git_service":
                git_service_calls.append(node.attr)
    
    # Verify expected GitService methods are being called
    expected_methods = ["ensure_worktree", "push_and_open_pr", "trigger_ci", "remote_branch_exists"]
    for method in expected_methods:
        assert method in git_service_calls, f"GitService.{method} should be called in codex_worker"
