#!/usr/bin/env python3
"""Launcher for the TasksGodzilla CLI."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasksgodzilla.cli.main import main  # noqa: E402


if __name__ == "__main__":
    main()

