#!/usr/bin/env python3
"""Lint: every script in scripts/ should have a module docstring.

A reviewer landing on `scripts/` should be able to `python <script> --help`
or read the first 5 lines and understand what the script does. This check
fails if any script's first non-shebang line isn't a docstring.

Usage:
    python scripts/docs_lint.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def has_module_docstring(p: Path) -> bool:
    lines = p.read_text(encoding="utf-8").splitlines()
    seen_code = False
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith("from __future__"):
            continue
        # First non-trivial line should be the docstring opener.
        if s.startswith('"""') or s.startswith("'''"):
            return True
        # If we hit code first, no docstring.
        return False
    return False


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    failures: list[str] = []
    n = 0
    for p in sorted(_HERE.glob("*.py")):
        if p.name == "__init__.py":
            continue
        n += 1
        if not has_module_docstring(p):
            failures.append(p.name)
            print(f"  FAIL: {p.name} (no module docstring)")
    print()
    if failures:
        print(f"FAIL: {len(failures)} of {n} scripts missing docstrings")
        return 1
    print(f"OK: all {n} scripts have module docstrings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
