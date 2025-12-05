#!/usr/bin/env python3
"""
Trigger CI pipelines for a protocol branch via gh or glab.
This script is a thin wrapper over deksdenflow.ci.trigger_ci.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deksdenflow.ci import trigger_ci  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger CI for a protocol branch.")
    parser.add_argument("--branch", required=True, help="Branch name (NNNN-task).")
    parser.add_argument("--repo-root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--platform", choices=["github", "gitlab"], required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    triggered = trigger_ci(args.platform, repo_root, args.branch)
    if not triggered:
        sys.exit(1)


if __name__ == "__main__":
    main()
