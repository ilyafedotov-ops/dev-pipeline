import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import codex
from .errors import CodexCommandError
from tasksgodzilla.engines import EngineRequest, registry
from tasksgodzilla.logging import get_logger
import tasksgodzilla.engines_codex  # noqa: F401 - ensure Codex engine is registered

log = get_logger(__name__)


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
    repo_root = protocol_root.parent.parent
    git_status = "(not a git repo)"
    last_commit = "(no commits yet)"
    if (repo_root / ".git").exists():
        try:
            git_status = codex.run_process(
                ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True
            ).stdout.strip()
            last_commit = codex.run_process(
                ["git", "log", "-1", "--pretty=format:%s"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except Exception:
            git_status = "(git status unavailable)"
            last_commit = last_commit or "(no commits yet)"

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
    """
    Guardrail: require an explicit VERDICT line. If the report is empty or the
    verdict is missing, treat it as FAIL to avoid false positives.
    """
    if not report_text.strip():
        return "FAIL"
    lines = [line.strip().upper() for line in report_text.splitlines() if line.strip()]
    verdict_line = next((line for line in reversed(lines) if line.startswith("VERDICT")), None)
    if verdict_line is None:
        return "FAIL"
    return "FAIL" if "FAIL" in verdict_line else "PASS"


def run_quality_check(
    protocol_root: Path,
    step_file: Path,
    model: str,
    prompt_file: Path,
    sandbox: str = "read-only",
    report_file: Optional[Path] = None,
    max_tokens: Optional[int] = None,
    token_budget_mode: str = "strict",
    engine_id: Optional[str] = None,
) -> QualityResult:
    log.info(
        "qa_run_start",
        extra={
            "protocol_root": str(protocol_root),
            "step_file": str(step_file),
            "model": model,
            "prompt_file": str(prompt_file),
            "sandbox": sandbox,
            "engine_id": engine_id or "default",
        },
    )
    if shutil.which("codex") is None:
        log.error("codex_cli_missing", extra={"protocol_root": str(protocol_root)})
        raise FileNotFoundError("codex CLI not found in PATH")
    if not step_file.is_file():
        log.error("qa_step_missing", extra={"step_file": str(step_file), "protocol_root": str(protocol_root)})
        raise FileNotFoundError(f"Step file not found: {step_file}")
    if not prompt_file.is_file():
        log.error("qa_prompt_missing", extra={"prompt_file": str(prompt_file), "protocol_root": str(protocol_root)})
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    prompt_prefix = prompt_file.read_text(encoding="utf-8")
    prompt_body = build_prompt(protocol_root, step_file)
    full_prompt = f"{prompt_prefix}\n\n{prompt_body}"

    report_path = report_file if report_file else protocol_root / "quality-report.md"

    codex.enforce_token_budget(full_prompt, max_tokens, f"qa:{step_file.name}", mode=token_budget_mode)

    # Route QA through the engine registry. If the chosen engine is Codex, call
    # the CLI directly so existing mocks against `codex.run_process` continue to work.
    engine = registry.get(engine_id) if engine_id else registry.get_default()
    if engine.metadata.id == "codex":
        log.info(
            "qa_exec_codex",
            extra={
                "protocol_root": str(protocol_root),
                "step_file": str(step_file),
                "model": model,
                "sandbox": sandbox,
            },
        )
        proc = codex.run_process(
            [
                "codex",
                "exec",
                "-m",
                model,
                "--cd",
                str(protocol_root.parent.parent),
                "--sandbox",
                sandbox,
                "--skip-git-repo-check",
                "-",
            ],
            cwd=protocol_root.parent.parent,
            capture_output=True,
            text=True,
            input_text=full_prompt,
            check=True,
        )
        report_text = (proc.stdout or "").strip()
        result_metadata = {"returncode": proc.returncode, "sandbox": sandbox}
    else:
        log.info(
            "qa_exec_engine",
            extra={
                "protocol_root": str(protocol_root),
                "step_file": str(step_file),
                "model": model,
                "engine_id": engine.metadata.id,
                "sandbox": sandbox,
            },
        )
        req = EngineRequest(
            project_id=0,
            protocol_run_id=0,
            step_run_id=0,
            model=model,
            prompt_files=[],
            working_dir=str(protocol_root.parent.parent),
            extra={
                "prompt_text": full_prompt,
                "sandbox": sandbox,
            },
        )
        result = engine.qa(req)
        report_text = (result.stdout or "").strip()
        result_metadata = result.metadata

    report_path.write_text(report_text, encoding="utf-8")
    verdict = determine_verdict(report_text)

    log.info(
        "qa_run_complete",
        extra={
            "protocol_root": str(protocol_root),
            "step_file": str(step_file),
            "report_path": str(report_path),
            "verdict": verdict,
            "engine_id": engine.metadata.id,
        },
    )
    return QualityResult(report_path=report_path, verdict=verdict, output=report_text)
