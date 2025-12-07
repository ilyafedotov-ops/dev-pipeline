#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasksgodzilla.pipeline import (  # noqa: E402
    create_worktree,
    decompose_step_prompt,
    detect_repo_root,
    execute_step_prompt,
    load_templates,
    next_protocol_number,
    open_draft_pr_or_mr,
    planning_prompt,
    prompt,
    run,
    run_codex_exec,
    run_pipeline,
    slugify,
    write_protocol_files,
)
from tasksgodzilla.config import load_config  # noqa: E402
from tasksgodzilla.logging import (  # noqa: E402
    init_cli_logging,
    json_logging_from_env,
    EXIT_DEP_MISSING,
    EXIT_RUNTIME_ERROR,
    get_logger,
)

logger = get_logger(__name__)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive TasksGodzilla_Ilyas_Edition_1.0 protocol pipeline using Codex CLI.",
    )
    parser.add_argument(
        "--base-branch",
        help="Base branch to branch from (default: main).",
    )
    parser.add_argument(
        "--short-name",
        help="Task short name for protocol/branch (Task-short-name, e.g. 'user-onboarding').",
    )
    parser.add_argument(
        "--description",
        help="Human-readable description of the task.",
    )
    parser.add_argument(
        "--planning-model",
        help="Model for planning step (default from PROTOCOL_PLANNING_MODEL or gpt-5.1-high).",
    )
    parser.add_argument(
        "--decompose-model",
        help="Model for step decomposition (default from PROTOCOL_DECOMPOSE_MODEL or gpt-5.1).",
    )
    parser.add_argument(
        "--exec-model",
        help="Model for executing a specific step (default from PROTOCOL_EXEC_MODEL or codex-5.1-max-xhigh).",
    )
    parser.add_argument(
        "--run-step",
        help="Relative step filename inside the protocol folder to auto-run (e.g. 01-some-step.md).",
    )
    parser.add_argument(
        "--pr-platform",
        choices=["github", "gitlab"],
        help="If set, auto-commit protocol artifacts, push branch, and create Draft PR/MR on the chosen platform.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    config = load_config()
    init_cli_logging(config.log_level, json_output=json_logging_from_env())
    cli_args = parse_args()
    try:
        run_pipeline(cli_args)
    except FileNotFoundError as e:
        logger.error("Dependency missing", extra={"error": str(e), "error_type": e.__class__.__name__})
        sys.exit(EXIT_DEP_MISSING)
    except subprocess.CalledProcessError as e:
        logger.error(
            "Command failed",
            extra={"error": str(e), "returncode": e.returncode, "error_type": e.__class__.__name__},
        )
        sys.exit(e.returncode or EXIT_RUNTIME_ERROR)
    except Exception as e:  # pragma: no cover - defensive
        logger.error("protocol_pipeline_unhandled_error", extra={"error": str(e), "error_type": e.__class__.__name__})
        sys.exit(EXIT_RUNTIME_ERROR)
