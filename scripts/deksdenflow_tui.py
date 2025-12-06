#!/usr/bin/env python3
"""Launch the Textual TUI for DeksdenFlow."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deksdenflow.cli.tui import run_tui  # noqa: E402


if __name__ == "__main__":
    run_tui()

