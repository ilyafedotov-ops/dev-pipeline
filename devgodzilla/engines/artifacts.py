"""
DevGodzilla Artifact Writer

Utilities for capturing and storing execution artifacts.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Artifact:
    """Represents an execution artifact."""
    name: str
    kind: str  # e.g., "output", "log", "diff", "screenshot"
    path: Path
    size_bytes: int = 0
    hash: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ArtifactWriter:
    """
    Captures and stores execution artifacts.
    
    Manages:
    - Output files from engine execution
    - Log files
    - Diff/patch files
    - QA reports
    - Screenshots and other media
    
    Example:
        writer = ArtifactWriter(artifacts_dir)
        
        # Write text artifact
        artifact = writer.write_text(
            name="output",
            content="Generated code...",
            kind="output",
        )
        
        # Write JSON artifact
        writer.write_json(
            name="qa_report",
            data={"passed": True, "findings": []},
            kind="report",
        )
    """

    def __init__(
        self,
        artifacts_dir: Path,
        *,
        run_id: Optional[str] = None,
        step_run_id: Optional[int] = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.run_id = run_id
        self.step_run_id = step_run_id
        self._artifacts: List[Artifact] = []

    def _ensure_dir(self, subdir: Optional[str] = None) -> Path:
        """Ensure artifacts directory exists."""
        target = self.artifacts_dir
        if subdir:
            target = target / subdir
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _hash_content(self, content: bytes) -> str:
        """Generate SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()[:16]

    def write_text(
        self,
        name: str,
        content: str,
        kind: str = "output",
        *,
        extension: str = ".txt",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """
        Write text content as an artifact.
        
        Args:
            name: Artifact name (becomes filename)
            content: Text content
            kind: Artifact kind (output, log, etc.)
            extension: File extension
            metadata: Optional metadata
            
        Returns:
            Created Artifact
        """
        target_dir = self._ensure_dir()
        filename = f"{name}{extension}"
        path = target_dir / filename
        
        content_bytes = content.encode("utf-8")
        path.write_bytes(content_bytes)
        
        artifact = Artifact(
            name=name,
            kind=kind,
            path=path,
            size_bytes=len(content_bytes),
            hash=self._hash_content(content_bytes),
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        
        self._artifacts.append(artifact)
        
        logger.debug(
            "artifact_written",
            extra={"name": name, "kind": kind, "size": len(content_bytes)},
        )
        
        return artifact

    def write_json(
        self,
        name: str,
        data: Any,
        kind: str = "data",
        *,
        indent: int = 2,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """
        Write JSON data as an artifact.
        
        Args:
            name: Artifact name
            data: JSON-serializable data
            kind: Artifact kind
            indent: JSON indentation
            metadata: Optional metadata
            
        Returns:
            Created Artifact
        """
        content = json.dumps(data, indent=indent, default=str)
        return self.write_text(
            name=name,
            content=content,
            kind=kind,
            extension=".json",
            metadata=metadata,
        )

    def write_bytes(
        self,
        name: str,
        content: bytes,
        kind: str = "binary",
        *,
        extension: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """
        Write binary content as an artifact.
        
        Args:
            name: Artifact name
            content: Binary content
            kind: Artifact kind
            extension: File extension
            metadata: Optional metadata
            
        Returns:
            Created Artifact
        """
        target_dir = self._ensure_dir()
        filename = f"{name}{extension}"
        path = target_dir / filename
        
        path.write_bytes(content)
        
        artifact = Artifact(
            name=name,
            kind=kind,
            path=path,
            size_bytes=len(content),
            hash=self._hash_content(content),
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        
        self._artifacts.append(artifact)
        return artifact

    def copy_file(
        self,
        source: Path,
        name: Optional[str] = None,
        kind: str = "file",
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """
        Copy a file to artifacts directory.
        
        Args:
            source: Source file path
            name: Optional artifact name (defaults to source filename)
            kind: Artifact kind
            metadata: Optional metadata
            
        Returns:
            Created Artifact
        """
        import shutil
        
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")
        
        target_dir = self._ensure_dir()
        target_name = name or source.name
        target = target_dir / target_name
        
        shutil.copy2(source, target)
        
        content = target.read_bytes()
        artifact = Artifact(
            name=target_name,
            kind=kind,
            path=target,
            size_bytes=len(content),
            hash=self._hash_content(content),
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        
        self._artifacts.append(artifact)
        return artifact

    def write_log(
        self,
        name: str,
        lines: List[str],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """Write log lines as an artifact."""
        content = "\n".join(lines)
        return self.write_text(
            name=name,
            content=content,
            kind="log",
            extension=".log",
            metadata=metadata,
        )

    def write_diff(
        self,
        name: str,
        diff_content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """Write diff/patch content as an artifact."""
        return self.write_text(
            name=name,
            content=diff_content,
            kind="diff",
            extension=".diff",
            metadata=metadata,
        )

    def list_artifacts(self) -> List[Artifact]:
        """List all written artifacts."""
        return self._artifacts.copy()

    def get_manifest(self) -> Dict[str, Any]:
        """Get manifest of all artifacts."""
        return {
            "run_id": self.run_id,
            "step_run_id": self.step_run_id,
            "artifacts_dir": str(self.artifacts_dir),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": [
                {
                    "name": a.name,
                    "kind": a.kind,
                    "path": str(a.path),
                    "size_bytes": a.size_bytes,
                    "hash": a.hash,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "metadata": a.metadata,
                }
                for a in self._artifacts
            ],
        }

    def write_manifest(self) -> Artifact:
        """Write manifest file for all artifacts."""
        return self.write_json(
            name="manifest",
            data=self.get_manifest(),
            kind="manifest",
        )


def get_run_artifacts_dir(
    runs_dir: Path,
    run_id: str,
) -> Path:
    """Get artifacts directory for a specific run."""
    return runs_dir / run_id / "artifacts"


def get_step_artifacts_dir(
    runs_dir: Path,
    run_id: str,
    step_run_id: int,
) -> Path:
    """Get artifacts directory for a specific step run."""
    return runs_dir / run_id / "steps" / str(step_run_id) / "artifacts"
