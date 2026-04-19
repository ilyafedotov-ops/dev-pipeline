from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = (
    REPO_ROOT / "devgodzilla" / "services",
    REPO_ROOT / "devgodzilla" / "api" / "routes",
    REPO_ROOT / "devgodzilla" / "engines",
)


def _runtime_files() -> list[Path]:
    files: list[Path] = []
    for directory in RUNTIME_DIRS:
        files.extend(sorted(path for path in directory.glob("*.py") if path.name != "__init__.py"))
    return files


def test_runtime_modules_bind_structured_logger() -> None:
    missing = []
    for path in _runtime_files():
        if "get_logger(" not in path.read_text(encoding="utf-8"):
            missing.append(path.relative_to(REPO_ROOT).as_posix())
    assert not missing, f"Runtime modules missing structured logger wiring: {missing}"


def test_runtime_modules_do_not_use_print_calls() -> None:
    offenders = []
    for path in _runtime_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}")
    assert not offenders, f"Runtime modules must use structured logging instead of print(): {offenders}"
