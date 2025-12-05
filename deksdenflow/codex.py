import subprocess
from pathlib import Path
from typing import List, Optional
import math

from .logging import get_logger

log = get_logger(__name__)


def run_process(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = False,
    text: bool = True,
    input_text: Optional[str] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run a subprocess command with consistent defaults across the codebase.

    capture_output=True enables stdout/stderr capture; text=True returns strings.
    input_text (string) is encoded when text=True.
    """
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        capture_output=capture_output,
        text=text,
        input=input_text if input_text is not None else None,
    )


def run_command(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a subprocess command with optional working directory."""
    return run_process(cmd, cwd=cwd, capture_output=False, text=True, check=True)


def estimate_tokens(text: str) -> int:
    """
    Rough token estimator: 4 characters per token heuristic.
    """
    return max(1, math.ceil(len(text) / 4))


def enforce_token_budget(prompt_text: str, max_tokens: Optional[int], context: str, mode: str = "strict") -> None:
    """
    Enforce a soft token budget by estimating tokens before invoking Codex.
    Modes:
    - strict (default): raise ValueError if estimate exceeds max_tokens.
    - warn: log a warning but do not raise.
    - off: do nothing.
    """
    if not max_tokens or mode == "off":
        return
    estimated = estimate_tokens(prompt_text)
    if estimated > max_tokens:
        message = (
            f"Estimated prompt tokens ({estimated}) exceed configured limit ({max_tokens}) for {context}. "
            "Reduce context or raise the budget."
        )
        if mode == "warn":
            log.warning("Token budget exceeded", extra={"context": context, "estimated_tokens": estimated, "max_tokens": max_tokens})
            return
        raise ValueError(message)
    log.debug("Token budget ok", extra={"context": context, "estimated_tokens": estimated, "max_tokens": max_tokens})


def run_codex_exec(
    model: str,
    cwd: Path,
    prompt_text: str,
    sandbox: str = "read-only",
    output_schema: Optional[Path] = None,
    output_last_message: Optional[Path] = None,
) -> None:
    """Invoke codex exec with common flags."""
    cmd = [
        "codex",
        "exec",
        "-m",
        model,
        "--sandbox",
        sandbox,
        "--cd",
        str(cwd),
        "--skip-git-repo-check",
    ]
    if output_schema is not None:
        cmd.extend(["--output-schema", str(output_schema)])
    if output_last_message is not None:
        cmd.extend(["--output-last-message", str(output_last_message)])
    cmd.append("-")
    subprocess.run(
        cmd,
        input=prompt_text.encode("utf-8"),
        check=True,
    )
