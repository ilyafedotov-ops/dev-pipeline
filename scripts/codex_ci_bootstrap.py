#!/usr/bin/env python3
"""
Run Codex discovery for CI bootstrap, with run registry logging.

Replaces the previous bash wrapper so tests can import functions directly.
"""

import argparse
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    Invoke codex exec with the discovery prompt.

    Streams Codex output to stdout while also teeing it into:
    - the run registry log (when available)
    - `codex-discovery.log` inside the target repo for easy inspection.

    Returns the process return code.
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

    repo_log_path = repo_root / "codex-discovery.log"
    repo_log_path.parent.mkdir(parents=True, exist_ok=True)
    run_log_file = None
    if RUN_LOG_PATH:
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        run_log_file = RUN_LOG_PATH.open("a", encoding="utf-8")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(prompt_text)
        proc.stdin.close()

        with repo_log_path.open("w", encoding="utf-8") as repo_log_file:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                repo_log_file.write(line)
                if run_log_file:
                    run_log_file.write(line)

        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)
        return rc
    finally:
        if run_log_file:
            run_log_file.close()


def run_opencode_discovery(
    repo_root: Path,
    model: str,
    prompt_file: Path,
    strict: bool = True,
) -> int:
    """
    Invoke the OpenCode engine via the TasksGodzilla engine registry.
    Writes output to stdout and to opencode-discovery.log in the repo.
    """
    from tasksgodzilla.engines import EngineRequest, registry
    import tasksgodzilla.engines_opencode  # noqa: F401

    prompt_text = prompt_file.read_text(encoding="utf-8")
    engine = registry.get("opencode")
    req = EngineRequest(
        project_id=0,
        protocol_run_id=0,
        step_run_id=0,
        model=model,
        prompt_files=[],
        working_dir=str(repo_root),
        extra={"prompt_text": prompt_text, "sandbox": "workspace-write"},
    )
    result = engine.execute(req)
    out = (result.stdout or "")

    repo_log_path = repo_root / "opencode-discovery.log"
    repo_log_path.parent.mkdir(parents=True, exist_ok=True)
    repo_log_path.write_text(out, encoding="utf-8")
    sys.stdout.write(out)
    sys.stdout.flush()
    return 0

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex discovery to bootstrap CI.")
    parser.add_argument("--engine", default="codex", choices=["codex", "opencode"])
    parser.add_argument("--model", default=None, help="Model to use (engine-specific default if omitted).")
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

    if args.engine == "opencode":
        model = args.model or "zai-coding-plan/glm-4.6"
    else:
        model = args.model or "gpt-5.1-codex-max"

    if args.engine == "codex" and not shutil.which("codex"):
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
            "engine": args.engine,
            "model": model,
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
        if args.engine == "opencode":
            rc = run_opencode_discovery(repo_root=repo_root, model=model, prompt_file=prompt_file, strict=args.strict)
        else:
            proc = run_codex_discovery(
                repo_root=repo_root,
                model=model,
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
