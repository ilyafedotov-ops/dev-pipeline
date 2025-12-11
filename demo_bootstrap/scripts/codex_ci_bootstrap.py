#!/usr/bin/env python3
"""
Run Codex discovery for CI bootstrap, with run registry logging.

Replaces the previous bash wrapper so tests can import functions directly.
"""

import argparse
import shutil
import sys
import uuid
from pathlib import Path
from typing import Optional

from tasksgodzilla.codex import run_process
from tasksgodzilla.config import load_config
from tasksgodzilla.logging import get_logger, setup_logging, json_logging_from_env, log_extra
from tasksgodzilla.run_registry import RunRegistry
from tasksgodzilla.storage import create_database

log = get_logger(__name__)
RUN_LOG_PATH: Optional[Path] = None


def run_codex_discovery(
    repo_root: Path,
    model: str,
    prompt_file: Path,
    sandbox: str = "workspace-write",
    skip_git_check: bool = False,
    strict: bool = True,
):
    """
    Invoke codex exec with the discovery prompt. Returns the completed process.
    """
    cmd = [
        "codex",
        "exec",
        "-m",
        model,
        "--cd",
        str(repo_root),
        "--sandbox",
        sandbox,
    ]
    if skip_git_check:
        cmd.append("--skip-git-repo-check")
    cmd.append("-")

    prompt_text = prompt_file.read_text(encoding="utf-8")
    proc = run_process(cmd, cwd=repo_root, capture_output=True, text=True, input_text=prompt_text, check=True)
    if RUN_LOG_PATH:
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RUN_LOG_PATH.open("a", encoding="utf-8") as f:
            if proc.stdout:
                f.write(proc.stdout)
            if proc.stderr:
                f.write("\n[stderr]\n")
                f.write(proc.stderr)
    return proc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex discovery to bootstrap CI.")
    parser.add_argument("--model", default="gpt-5.1-codex-max")
    parser.add_argument("--prompt-file", default="prompts/repo-discovery.prompt.md")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--skip-git-check", action="store_true", help="Skip git repo check in Codex CLI")
    parser.add_argument("--no-strict", dest="strict", action="store_false", help="Disable strict mode if used by downstream callers")
    parser.add_argument("--run-id", default=None)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    setup_logging(json_output=json_logging_from_env())

    if not shutil.which("codex"):
        print("[codex-ci-bootstrap] codex CLI not found in PATH", file=sys.stderr)
        return 127

    repo_root = Path(args.repo_root).resolve()
    prompt_file = Path(args.prompt_file).resolve()
    if not prompt_file.exists():
        print(f"[codex-ci-bootstrap] prompt not found: {prompt_file}", file=sys.stderr)
        return 1

    config = load_config()
    db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=config.db_pool_size)
    db.init_schema()
    registry = RunRegistry(db)
    run_id = args.run_id or str(uuid.uuid4())
    run = registry.start_run(
        "codex_ci_bootstrap",
        run_id=run_id,
        params={
            "model": args.model,
            "prompt_file": str(prompt_file),
            "repo_root": str(repo_root),
            "sandbox": args.sandbox,
            "skip_git_check": args.skip_git_check,
            "strict": args.strict,
        },
    )

    global RUN_LOG_PATH
    RUN_LOG_PATH = Path(run.log_path) if run.log_path else None
    try:
        proc = run_codex_discovery(
            repo_root=repo_root,
            model=args.model,
            prompt_file=prompt_file,
            sandbox=args.sandbox,
            skip_git_check=args.skip_git_check,
            strict=args.strict,
        )
        rc = getattr(proc, "returncode", 0) if proc is not None else 0
        registry.mark_succeeded(run_id, result={"returncode": rc})
        log.info("codex_ci_bootstrap_complete", extra=log_extra(run_id=run_id))
        return rc
    except Exception as exc:  # pragma: no cover - passthrough for CLI
        registry.mark_failed(run_id, error=str(exc))
        log.error("codex_ci_bootstrap_failed", extra=log_extra(run_id=run_id, error=str(exc)))
        raise


if __name__ == "__main__":
    sys.exit(main())
