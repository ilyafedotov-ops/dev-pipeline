#!/usr/bin/env python3
"""
Run TasksGodzilla multi-pass discovery pipeline on an existing repo.

Allows re-running specific artifacts without a full onboarding flow.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasksgodzilla.config import load_config  # noqa: E402
from tasksgodzilla.logging import init_cli_logging, json_logging_from_env, get_logger, EXIT_DEP_MISSING, EXIT_RUNTIME_ERROR  # noqa: E402
from tasksgodzilla.project_setup import run_codex_discovery_pipeline  # noqa: E402

log = get_logger(__name__)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-pass discovery and generate artifacts.")
    parser.add_argument("--repo-root", default=".", help="Repository root to analyze.")
    parser.add_argument("--engine", default=None, help="Engine to use for discovery (codex|opencode). Defaults to TASKSGODZILLA_DEFAULT_ENGINE_ID or codex.")
    parser.add_argument("--model", default=None, help="Codex model to use (default PROTOCOL_DISCOVERY_MODEL or gpt-5.1-codex-max).")
    parser.add_argument("--sandbox", default="workspace-write", help="Codex sandbox (default: workspace-write).")
    parser.add_argument(
        "--artifacts",
        default="inventory,architecture,api_reference,ci_notes",
        help="Comma-separated stages to run: inventory,architecture,api_reference,ci_notes",
    )
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional Codex timeout per stage.")
    parser.add_argument("--strict", action="store_true", help="Fail if prompts/Codex missing.")
    parser.add_argument("--skip-git-check", action="store_true", help="Pass --skip-git-repo-check to Codex.")
    return parser.parse_args(argv)


def main() -> int:
    config = load_config()
    init_cli_logging(config.log_level, json_output=json_logging_from_env())
    args = parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        log.error("repo_root_missing", extra={"repo_root": str(repo_root)})
        return EXIT_RUNTIME_ERROR

    engine_id = args.engine or os.environ.get("PROTOCOL_DISCOVERY_ENGINE") or getattr(config, "default_engine_id", None) or "codex"
    env_model = os.environ.get("PROTOCOL_DISCOVERY_MODEL")
    if args.model:
        model = args.model
    elif env_model:
        model = env_model
    elif engine_id == "opencode":
        from tasksgodzilla.engines import registry
        import tasksgodzilla.engines_opencode  # noqa: F401

        model = registry.get("opencode").metadata.default_model or "zai-coding-plan/glm-4.6"
    else:
        model = "gpt-5.1-codex-max"
    artifacts = [a.strip() for a in args.artifacts.split(",") if a.strip()]

    try:
        if engine_id == "opencode":
            from tasksgodzilla.engines import EngineRequest, registry
            import tasksgodzilla.engines_opencode  # noqa: F401
            from tasksgodzilla.project_setup import _resolve_prompt  # type: ignore

            stage_map: dict[str, str] = {
                "inventory": "discovery-inventory.prompt.md",
                "architecture": "discovery-architecture.prompt.md",
                "api_reference": "discovery-api-reference.prompt.md",
                "ci_notes": "discovery-ci-notes.prompt.md",
            }
            selected = list(stage_map.keys()) if artifacts is None else artifacts
            engine = registry.get("opencode")
            log_path = repo_root / "opencode-discovery.log"
            for stage in selected:
                prompt_name = stage_map.get(stage)
                if not prompt_name:
                    continue
                prompt_path = _resolve_prompt(repo_root, prompt_name)
                if not prompt_path:
                    if args.strict:
                        raise FileNotFoundError(f"discovery prompt missing: {prompt_name}")
                    continue
                prompt_text = prompt_path.read_text(encoding="utf-8")
                req = EngineRequest(
                    project_id=0,
                    protocol_run_id=0,
                    step_run_id=0,
                    model=model,
                    prompt_files=[],
                    working_dir=str(repo_root),
                    extra={"prompt_text": prompt_text, "sandbox": "workspace-write", "timeout_seconds": args.timeout_seconds},
                )
                result = engine.execute(req)
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n\n===== discovery stage: {stage} ({prompt_name}) =====\n")
                    f.write((result.stdout or "") + "\n")
        else:
            run_codex_discovery_pipeline(
                repo_root=repo_root,
                model=model,
                sandbox=args.sandbox,
                skip_git_check=args.skip_git_check,
                strict=args.strict,
                timeout_seconds=args.timeout_seconds,
                artifacts=artifacts,
            )
    except FileNotFoundError as exc:
        log.error("discovery_dependency_missing", extra={"error": str(exc)})
        return EXIT_DEP_MISSING
    except Exception as exc:  # pragma: no cover
        log.error("discovery_pipeline_failed", extra={"error": str(exc), "error_type": exc.__class__.__name__})
        return EXIT_RUNTIME_ERROR
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
