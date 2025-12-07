#!/usr/bin/env python3
"""
Run Codex as a QA orchestrator/validator for a given protocol step.
This script is now a thin wrapper over the reusable tasksgodzilla.qa module.
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasksgodzilla.config import load_config  # noqa: E402
from tasksgodzilla.logging import (
    init_cli_logging,
    json_logging_from_env,
    EXIT_DEP_MISSING,
    EXIT_RUNTIME_ERROR,
    get_logger,
)  # noqa: E402
from tasksgodzilla.qa import QualityResult, run_quality_check  # noqa: E402

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    config = load_config()
    parser = argparse.ArgumentParser(description="Run Codex QA orchestrator for a protocol step.")
    parser.add_argument(
        "--protocol-root",
        required=True,
        help="Path to protocol folder (.protocols/NNNN-[Task-short-name]).",
    )
    parser.add_argument(
        "--step-file",
        required=True,
        help="Step file name inside protocol folder (e.g., 01-some-step.md).",
    )
    parser.add_argument(
        "--model",
        default=config.qa_model or os.environ.get("PROTOCOL_QA_MODEL", "codex-5.1-max"),
        help="Codex model to use (default: config, env PROTOCOL_QA_MODEL, or codex-5.1-max).",
    )
    parser.add_argument(
        "--prompt-file",
        default="prompts/quality-validator.prompt.md",
        help="Prompt file to prepend (default: prompts/quality-validator.prompt.md).",
    )
    parser.add_argument(
        "--report-file",
        default=None,
        help="Where to write the QA report (default: protocol_root/quality-report.md).",
    )
    parser.add_argument(
        "--sandbox",
        default="read-only",
        help="Codex sandbox mode (default: read-only).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    init_cli_logging(config.log_level, json_output=json_logging_from_env())

    protocol_root = Path(args.protocol_root).resolve()
    step_path = protocol_root / args.step_file
    prompt_path = Path(args.prompt_file).resolve()
    report_path = Path(args.report_file) if args.report_file else None

    log.info(
        "quality_orchestrator_start",
        extra={
            "protocol_root": str(protocol_root),
            "step_file": str(step_path),
            "prompt_file": str(prompt_path),
            "report_path": str(report_path) if report_path else None,
            "model": args.model,
            "sandbox": args.sandbox,
        },
    )
    try:
        qa_result: QualityResult = run_quality_check(
            protocol_root=protocol_root,
            step_file=step_path,
            model=args.model,
            prompt_file=prompt_path,
            sandbox=args.sandbox,
            report_file=report_path,
            max_tokens=config.max_tokens_per_step or config.max_tokens_per_protocol,
            token_budget_mode=config.token_budget_mode,
        )
    except FileNotFoundError as exc:
        log.error("quality_orchestrator_missing_dep", extra={"error": str(exc)})
        sys.exit(EXIT_DEP_MISSING)
    except Exception as exc:
        log.error(
            "quality_orchestrator_failed",
            extra={"error": str(exc), "error_type": exc.__class__.__name__},
        )
        sys.exit(EXIT_RUNTIME_ERROR)

    log.info(
        "quality_orchestrator_complete",
        extra={
            "report_path": str(qa_result.report_path),
            "verdict": qa_result.verdict,
        },
    )
    if qa_result.verdict.upper() == "FAIL":
        log.warning("quality_orchestrator_verdict_fail", extra={"report_path": str(qa_result.report_path)})
        sys.exit(EXIT_RUNTIME_ERROR)


if __name__ == "__main__":
    main()
