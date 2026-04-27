#!/usr/bin/env python3
"""Fail when tracked Python modules exceed a configured line budget."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable


def _normalize_path(path: str | Path) -> str:
    return Path(path).resolve().as_posix()


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _iter_violations(
    files: Iterable[str],
    max_lines: int,
    ignored_paths: set[str],
) -> Iterable[tuple[str, int]]:
    for raw_path in files:
        path = Path(raw_path)
        normalized = _normalize_path(path)
        if normalized in ignored_paths:
            continue
        if not path.exists():
            raise FileNotFoundError(f"file not found: {raw_path}")
        if _count_lines(path) > max_lines:
            yield (path.as_posix(), _count_lines(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    parser.add_argument("--max-lines", type=int, required=True)
    parser.add_argument("--ignore", action="append", default=[])
    args = parser.parse_args()

    ignored_paths = {_normalize_path(path) for path in args.ignore}

    violations = list(_iter_violations(args.files, args.max_lines, ignored_paths))
    if not violations:
        return 0

    for path, line_count in violations:
        print(f"{path}: {line_count} lines exceeds max {args.max_lines}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
