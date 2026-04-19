from __future__ import annotations

from pathlib import Path

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class WorkspacePathError(RuntimeError):
    """Raised when a project/run has no safe workspace root."""


def resolve_workspace_root(run, project) -> Path:
    """Resolve the concrete workspace root for a run/project pair."""
    missing: list[tuple[str, Path]] = []

    worktree_path = getattr(run, "worktree_path", None)
    if worktree_path:
        candidate = Path(worktree_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        missing.append(("worktree_path", candidate))

    local_path = getattr(project, "local_path", None)
    if local_path:
        candidate = Path(local_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        missing.append(("local_path", candidate))

    if missing:
        details = ", ".join(f"{name}={path}" for name, path in missing)
        raise WorkspacePathError(f"Workspace path does not exist: {details}")

    raise WorkspacePathError("Project has no resolved workspace path")


def resolve_protocol_root(run, workspace_root: Path) -> Path:
    """Resolve the protocol directory within the workspace."""
    protocol_root = getattr(run, "protocol_root", None)
    if protocol_root:
        candidate = Path(protocol_root).expanduser()
        return candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()

    specs = workspace_root / "specs" / run.protocol_name
    protocols = workspace_root / ".protocols" / run.protocol_name
    if specs.exists():
        return specs
    if protocols.exists():
        return protocols
    return specs
