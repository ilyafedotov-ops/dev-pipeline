from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Tuple

from tasksgodzilla.logging import get_logger
from tasksgodzilla.storage import BaseDatabase

log = get_logger(__name__)


def _sha256_and_size(path: Path, *, chunk_size: int = 1024 * 1024) -> Tuple[Optional[str], Optional[int]]:
    try:
        stat = path.stat()
    except Exception:
        return None, None
    if not path.is_file():
        return None, int(getattr(stat, "st_size", 0) or 0)
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest(), int(stat.st_size)
    except Exception:
        return None, int(getattr(stat, "st_size", 0) or 0)


def register_run_artifact(
    db: BaseDatabase,
    *,
    run_id: str,
    name: str,
    kind: str,
    path: str,
) -> None:
    if path.startswith("windmill://"):
        db.upsert_run_artifact(run_id, name, kind=kind, path=path, sha256=None, bytes=None)
        return
    file_path = Path(path)
    sha256, size = _sha256_and_size(file_path)
    db.upsert_run_artifact(run_id, name, kind=kind, path=str(file_path), sha256=sha256, bytes=size)
