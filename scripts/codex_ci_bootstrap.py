#!/usr/bin/env python3
"""
Run Codex CLI to infer stack and fill CI scripts for the current repository.

This is a thin CLI wrapper around `deksdenflow.project_setup.run_codex_discovery`.
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deksdenflow.project_setup import run_codex_discovery  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use Codex CLI to infer stack and fill CI scripts for this repo."
    )
    parser.add_argument(
        "--model",
        default="gpt-5.1-codex-max",
        help="Codex model to use (default: gpt-5.1-codex-max).",
    )
    parser.add_argument(
        "--prompt-file",
        default="prompts/repo-discovery.prompt.md",
        help="Prompt file to feed Codex (default: prompts/repo-discovery.prompt.md).",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: current directory).",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        help="Codex sandbox mode (default: workspace-write).",
    )
    parser.add_argument(
        "--skip-git-check",
        action="store_true",
        help="Pass --skip-git-repo-check to codex exec.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_absolute():
        prompt_path = repo_root / prompt_path

    try:
        run_codex_discovery(
            repo_root=repo_root,
            model=args.model,
            prompt_file=prompt_path,
            sandbox=args.sandbox,
            skip_git_check=args.skip_git_check,
            strict=True,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"Codex discovery failed (exit {exc.returncode}): {exc}", file=sys.stderr)
        sys.exit(exc.returncode)

    print("Codex discovery complete. Review scripts/ci/* for generated commands.")


if __name__ == "__main__":
    main()
