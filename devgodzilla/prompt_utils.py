"""
DevGodzilla Prompt Utilities

Helper functions for prompt fingerprinting and versioning.
Used for auditing and tracking which prompt versions were used in executions.
"""

import hashlib
from pathlib import Path
from typing import Optional


def fingerprint_text(text: str, *, short: bool = True) -> str:
    """
    Return a stable fingerprint for the given prompt text.
    
    Short form keeps event metadata compact while still being unique for auditing.
    
    Args:
        text: The prompt text to fingerprint
        short: If True, return a 12-character hash; otherwise full SHA256
        
    Returns:
        Hash digest of the text
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:12] if short else digest


def fingerprint_file(path: Path, *, short: bool = True) -> str:
    """
    Hash the contents of a prompt file.
    
    Returns 'missing' if the file is not present so callers can record
    the absence rather than failing the workflow.
    
    Args:
        path: Path to the prompt file
        short: If True, return a 12-character hash; otherwise full SHA256
        
    Returns:
        Hash digest of the file contents, or 'missing' if file doesn't exist
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return "missing"
    digest = hashlib.sha256(data).hexdigest()
    return digest[:12] if short else digest


def prompt_version(prompt_path: Optional[Path]) -> str:
    """
    Convenience wrapper that fingerprints a prompt file when provided.
    
    Returns 'unknown' when no path is available.
    
    Args:
        prompt_path: Optional path to the prompt file
        
    Returns:
        12-character hash of the file, 'missing' if file doesn't exist,
        or 'unknown' if no path provided
    """
    if prompt_path is None:
        return "unknown"
    return fingerprint_file(prompt_path, short=True)


def content_hash(content: str) -> str:
    """
    Generate a short content hash for spec/configuration tracking.
    
    Args:
        content: String content to hash
        
    Returns:
        12-character SHA256 hash
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
