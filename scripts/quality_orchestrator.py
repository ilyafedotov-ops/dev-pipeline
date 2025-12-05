#!/usr/bin/env python3
"""
Run Codex as a QA orchestrator/validator for a given protocol step.
It collects plan/context/log, the step file, git status, and latest commit message,
then asks Codex (default model: codex-5.1-max) to produce a verdict and findings.
If the verdict is FAIL, this script exits 1 to stop the pipeline.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None, check=True, capture=True, input_text=None):
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=input_text.encode("utf-8") if input_text else None,
        check=check,
        capture_output=capture,
        text=True,
    )


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def build_prompt(protocol_root: Path, step_file: Path) -> str:
    plan = read_file(protocol_root / "plan.md")
    context = read_file(protocol_root / "context.md")
    log = read_file(protocol_root / "log.md")
    step = read_file(step_file)

    git_status = run(["git", "status", "--porcelain"], cwd=protocol_root.parent.parent).stdout.strip()
    last_commit = ""
    try:
        last_commit = run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=protocol_root.parent.parent,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        last_commit = "(no commits yet)"

    return f"""You are a QA orchestrator. Validate the current protocol step. Follow the checklist and output Markdown only (no fences).

plan.md:
{plan}

context.md:
{context}

log.md (may be empty):
{log}

Step file ({step_file.name}):
{step}

Git status (porcelain):
{git_status}

Latest commit message:
{last_commit}

Use the format from the quality-validator prompt. If any blocking issue, verdict = FAIL."""


def main() -> None:
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
        default=os.environ.get("PROTOCOL_QA_MODEL", "codex-5.1-max"),
        help="Codex model to use (default: env PROTOCOL_QA_MODEL or codex-5.1-max).",
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
    args = parser.parse_args()

    if shutil.which("codex") is None:
        print("codex CLI not found in PATH. Install/configure codex first.", file=sys.stderr)
        sys.exit(1)

    protocol_root = Path(args.protocol_root).resolve()
    step_path = protocol_root / args.step_file
    if not step_path.is_file():
        print(f"Step file not found: {step_path}", file=sys.stderr)
        sys.exit(1)

    prompt_file = Path(args.prompt_file).resolve()
    if not prompt_file.is_file():
        print(f"Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)

    prompt_prefix = prompt_file.read_text(encoding="utf-8")
    prompt_body = build_prompt(protocol_root, step_path)
    full_prompt = f"{prompt_prefix}\n\n{prompt_body}"

    report_path = Path(args.report_file) if args.report_file else protocol_root / "quality-report.md"

    cmd = [
        "codex",
        "exec",
        "-m",
        args.model,
        "--cd",
        str(protocol_root.parent.parent),
        "--sandbox",
        args.sandbox,
        "-",
    ]

    result = run(cmd, input_text=full_prompt, capture=True, check=False)
    if result.returncode != 0:
        print("Codex QA run failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    report_text = result.stdout.strip()
    report_path.write_text(report_text, encoding="utf-8")
    print(f"QA report written to {report_path}")

    if "VERDICT" in report_text.upper():
        if "FAIL" in report_text.splitlines()[-1].upper() or "VERDICT: FAIL" in report_text.upper():
            print("QA verdict: FAIL")
            sys.exit(1)


if __name__ == "__main__":
    main()
