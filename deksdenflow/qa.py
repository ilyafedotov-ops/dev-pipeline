import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .codex import run_process, enforce_token_budget


@dataclass
class QualityResult:
    report_path: Path
    verdict: str
    output: str


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def build_prompt(protocol_root: Path, step_file: Path) -> str:
    plan = read_file(protocol_root / "plan.md")
    context = read_file(protocol_root / "context.md")
    log = read_file(protocol_root / "log.md")
    step = read_file(step_file)

    git_status = run_process(
        ["git", "status", "--porcelain"], cwd=protocol_root.parent.parent, capture_output=True, text=True
    ).stdout.strip()
    last_commit = ""
    try:
        last_commit = run_process(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=protocol_root.parent.parent,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
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


def determine_verdict(report_text: str) -> str:
    upper = report_text.upper()
    if "VERDICT: FAIL" in upper:
        return "FAIL"
    lines = [line.strip().upper() for line in report_text.splitlines() if line.strip()]
    if lines and lines[-1].startswith("VERDICT") and "FAIL" in lines[-1]:
        return "FAIL"
    return "PASS"


def run_quality_check(
    protocol_root: Path,
    step_file: Path,
    model: str,
    prompt_file: Path,
    sandbox: str = "read-only",
    report_file: Optional[Path] = None,
    max_tokens: Optional[int] = None,
    token_budget_mode: str = "strict",
) -> QualityResult:
    if shutil.which("codex") is None:
        raise FileNotFoundError("codex CLI not found in PATH")
    if not step_file.is_file():
        raise FileNotFoundError(f"Step file not found: {step_file}")
    if not prompt_file.is_file():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    prompt_prefix = prompt_file.read_text(encoding="utf-8")
    prompt_body = build_prompt(protocol_root, step_file)
    full_prompt = f"{prompt_prefix}\n\n{prompt_body}"

    report_path = report_file if report_file else protocol_root / "quality-report.md"

    cmd = [
        "codex",
        "exec",
        "-m",
        model,
        "--cd",
        str(protocol_root.parent.parent),
        "--sandbox",
        sandbox,
        "-",
    ]

    enforce_token_budget(full_prompt, max_tokens, f"qa:{step_file.name}", mode=token_budget_mode)

    result = run_process(cmd, input_text=full_prompt, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"codex exec failed with code {result.returncode}: {result.stderr}")

    report_text = result.stdout.strip()
    report_path.write_text(report_text, encoding="utf-8")
    verdict = determine_verdict(report_text)

    return QualityResult(report_path=report_path, verdict=verdict, output=report_text)
