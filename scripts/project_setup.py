#!/usr/bin/env python3
import argparse
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasksgodzilla.project_setup import (  # noqa: E402
    BASE_FILES,
    PLACEHOLDER,
    clone_repo,
    ensure_assets,
    ensure_base_branch,
    ensure_git_repo,
    ensure_remote_origin,
    run_codex_discovery,
)
try:
    from tasksgodzilla.config import load_config  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - fallback when deps missing
    load_config = None
try:
    from tasksgodzilla.logging import (  # type: ignore  # noqa: E402
        init_cli_logging,
        json_logging_from_env,
        EXIT_DEP_MISSING,
        EXIT_RUNTIME_ERROR,
        get_logger,
    )
except Exception:  # pragma: no cover - fallback when deps missing
    init_cli_logging = None
    json_logging_from_env = lambda: False  # type: ignore
    EXIT_DEP_MISSING = 3  # type: ignore
    EXIT_RUNTIME_ERROR = 1  # type: ignore
    get_logger = logging.getLogger  # type: ignore

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare an existing or new project with TasksGodzilla_Ilyas_Edition_1.0 starter assets.",
    )
    parser.add_argument(
        "--base-branch",
        default="main",
        help="Base branch name (default: main).",
    )
    parser.add_argument(
        "--init-if-needed",
        action="store_true",
        help="Initialize git repo if not already initialized.",
    )
    parser.add_argument(
        "--clone-url",
        help="Optional: git clone this repository before preparing assets.",
    )
    parser.add_argument(
        "--clone-dir",
        help="Optional: directory name for clone (default: repo name from URL).",
    )
    parser.add_argument(
        "--run-discovery",
        action="store_true",
        help="Run Codex-driven repository discovery/config prep (requires codex CLI).",
    )
    parser.add_argument(
        "--discovery-model",
        help="Model for discovery (default from PROTOCOL_DISCOVERY_MODEL or gpt-5.1-codex-max).",
    )
    return parser.parse_args()


def main() -> None:
    config = load_config() if load_config else SimpleNamespace(log_level="INFO")
    if init_cli_logging:
        init_cli_logging(getattr(config, "log_level", "INFO"), json_output=json_logging_from_env())
    args = parse_args()
    log.info(
        "project_setup_start",
        extra={
            "clone_url": args.clone_url,
            "clone_dir": args.clone_dir,
            "base_branch": args.base_branch,
            "run_discovery": args.run_discovery,
        },
    )

    repo_root: Path
    if args.clone_url:
        default_dir = (
            Path(args.clone_dir)
            if args.clone_dir
            else Path(args.clone_url.rstrip("/").split("/")[-1].replace(".git", ""))
        )
        repo_root = clone_repo(args.clone_url, default_dir.resolve())
    else:
        repo_root = ensure_git_repo(args.base_branch, args.init_if_needed)
    log.info("project_setup_repo_ready", extra={"repo_root": str(repo_root)})

    # Ensure subsequent commands operate inside the repo
    os.chdir(repo_root)
    repo_root = Path(os.getcwd())

    try:
        ensure_remote_origin(repo_root)
        ensure_base_branch(repo_root, args.base_branch)
        ensure_assets(repo_root)

        if args.run_discovery:
            discovery_model = args.discovery_model or os.environ.get("PROTOCOL_DISCOVERY_MODEL", "gpt-5.1-codex-max")
            run_codex_discovery(repo_root, discovery_model)
    except FileNotFoundError as exc:
        log.error("project_setup_dependency_missing", extra={"error": str(exc)})
        sys.exit(EXIT_DEP_MISSING)
    except Exception as exc:  # pragma: no cover - defensive
        log.error(
            "project_setup_failed",
            extra={"error": str(exc), "error_type": exc.__class__.__name__},
        )
        sys.exit(EXIT_RUNTIME_ERROR)

    log.info(
        "project_setup_complete",
        extra={"repo_root": str(repo_root)},
    )


if __name__ == "__main__":
    main()
