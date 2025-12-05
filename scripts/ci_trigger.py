#!/usr/bin/env python3
"""
Trigger CI pipelines for a protocol branch.
Uses gh or glab if available; otherwise prints a message.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def trigger_github(repo_root: Path, branch: str) -> None:
    if shutil.which("gh") is None:
        print("gh not available; cannot trigger GitHub Actions manually.")
        return
    try:
        run(["gh", "workflow", "run", "--ref", branch], cwd=repo_root)
        print(f"Triggered GitHub workflow for branch {branch}")
    except subprocess.CalledProcessError as exc:
        print(f"Failed to trigger GitHub workflow: {exc}")


def trigger_gitlab(repo_root: Path, branch: str) -> None:
    if shutil.which("glab") is None:
        print("glab not available; cannot trigger GitLab pipeline manually.")
        return
    try:
        run(["glab", "pipeline", "run", "--ref", branch], cwd=repo_root)
        print(f"Triggered GitLab pipeline for branch {branch}")
    except subprocess.CalledProcessError as exc:
        print(f"Failed to trigger GitLab pipeline: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger CI for a protocol branch.")
    parser.add_argument("--branch", required=True, help="Branch name (NNNN-task).")
    parser.add_argument("--repo-root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--platform", choices=["github", "gitlab"], required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if args.platform == "github":
        trigger_github(repo_root, args.branch)
    else:
        trigger_gitlab(repo_root, args.branch)


if __name__ == "__main__":
    main()
