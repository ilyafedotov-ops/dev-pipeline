import hashlib
from pathlib import Path
from typing import Optional


def fingerprint_text(text: str, short: bool = True) -> str:
    """
    Return a stable fingerprint for the given prompt text. Short form keeps
    event metadata compact while still being unique for auditing.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:12] if short else digest


def fingerprint_file(path: Path, short: bool = True) -> str:
    """
    Hash the contents of a prompt file. Returns 'missing' if the file is not present
    so callers can record the absence rather than failing the workflow.
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return "missing"
    digest = hashlib.sha256(data).hexdigest()
    return digest[:12] if short else digest


def prompt_version(prompt_path: Optional[Path]) -> str:
    """
    Convenience wrapper that fingerprints a prompt file when provided and
    returns 'unknown' when no path is available.
    """
    if prompt_path is None:
        return "unknown"
    return fingerprint_file(prompt_path, short=True)
