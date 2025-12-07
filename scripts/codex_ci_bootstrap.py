#!/usr/bin/env python3
"""
Run Codex CLI to infer stack and fill CI scripts for the current repository.

This is a thin CLI wrapper around `tasksgodzilla.project_setup.run_codex_discovery`.
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasksgodzilla.project_setup import run_codex_discovery  # noqa: E402
from tasksgodzilla.config import load_config  # noqa: E402
from tasksgodzilla.logging import (  # noqa: E402
    init_cli_logging,
    json_logging_from_env,
    EXIT_DEP_MISSING,
    EXIT_RUNTIME_ERROR,
    get_logger,
)

log = get_logger(__name__)


def main() -> None:
    config = load_config()
    init_cli_logging(config.log_level, json_output=json_logging_from_env())
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

    log.info(
        "codex_ci_bootstrap_start",
        extra={
            "repo_root": str(repo_root),
            "model": args.model,
            "prompt_path": str(prompt_path),
            "sandbox": args.sandbox,
            "skip_git_check": args.skip_git_check,
        },
    )
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
        log.error("codex_ci_bootstrap_missing_dep", extra={"error": str(exc)})
        sys.exit(EXIT_DEP_MISSING)
    except subprocess.CalledProcessError as exc:
        log.error(
            "codex_ci_bootstrap_failed",
            extra={"error": str(exc), "returncode": exc.returncode, "error_type": exc.__class__.__name__},
        )
        sys.exit(exc.returncode or EXIT_RUNTIME_ERROR)
    except Exception as exc:  # pragma: no cover - defensive
        log.error(
            "codex_ci_bootstrap_unexpected",
            extra={"error": str(exc), "error_type": exc.__class__.__name__},
        )
        sys.exit(EXIT_RUNTIME_ERROR)

    log.info("codex_ci_bootstrap_complete", extra={"repo_root": str(repo_root), "prompt_path": str(prompt_path)})


if __name__ == "__main__":
    main()
