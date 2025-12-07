#!/usr/bin/env python3
"""Launcher for the TasksGodzilla CLI."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# If a local .venv exists and we're not already using it, re-exec with that interpreter so
# `./scripts/tasksgodzilla_cli.py` works without activating the venv first.
VENV_DIR = PROJECT_ROOT / ".venv"
if os.environ.get("VIRTUAL_ENV") != str(VENV_DIR):
    candidates = [
        VENV_DIR / "bin" / "python",
        VENV_DIR / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists() and Path(sys.executable) != candidate:
            os.execv(str(candidate), [str(candidate), *sys.argv])

from tasksgodzilla.cli.main import main  # noqa: E402


if __name__ == "__main__":
    main()
