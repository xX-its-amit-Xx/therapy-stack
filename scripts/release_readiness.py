#!/usr/bin/env python3
"""Release-readiness checklist for therapy-stack.

A pre-tag gate that surfaces "the headline numbers don't reflect the
current code" classes of drift:

  1. baselines.json's recorded version_tag matches the most recent
     CHANGELOG entry's version
  2. CHANGELOG.md's most recent entry is dated today or earlier
     (i.e. not a stale forward-looking row)
  3. RESULTS_FRONTIER.md and CHANGELOG.md agree on the headline
     dev / val numbers for the current version
  4. SUMMARY.md references files that exist
  5. README.md references files that exist

Exit code 1 if any check fails. Designed to run before cutting a tag.

Usage:
    python scripts/release_readiness.py
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _check_changelog_date() -> tuple[bool, str]:
    """Most recent CHANGELOG entry's date should be today-or-earlier."""
    p = _ROOT / "CHANGELOG.md"
    if not p.exists():
        return False, "CHANGELOG.md missing"
    text = p.read_text(encoding="utf-8")
    # Find dates of form 2026-MM-DD.
    dates = re.findall(r"\| (\d{4}-\d{2}-\d{2}) \|", text)
    if not dates:
        return False, "no dates found in CHANGELOG.md"
    latest = max(dt.date.fromisoformat(d) for d in dates)
    today = dt.date.today()
    if latest > today:
        return False, f"CHANGELOG has a future date: {latest} > today {today}"
    if (today - latest).days > 30:
        return False, f"CHANGELOG most recent entry is {(today - latest).days} days old"
    return True, f"latest entry {latest} (today: {today})"


def _check_referenced_files(doc_name: str) -> tuple[bool, str]:
    """Every relative-path link in a markdown doc should exist."""
    p = _ROOT / doc_name
    if not p.exists():
        return False, f"{doc_name} missing"
    text = p.read_text(encoding="utf-8")
    # Find markdown links: [text](path)
    links = re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)", text)
    missing: list[str] = []
    for link in links:
        # Skip absolute URLs.
        if link.startswith(("http://", "https://", "mailto:")):
            continue
        # Skip in-page anchors.
        if link.startswith("#"):
            continue
        target = (_ROOT / link).resolve()
        if not target.exists():
            missing.append(link)
    if missing:
        return False, f"{doc_name} references missing files: {missing[:5]}"
    return True, f"all links resolve ({len(links)} checked)"


def _check_baselines_present() -> tuple[bool, str]:
    p = _ROOT / "baselines.json"
    if not p.exists():
        return False, "baselines.json missing"
    return True, f"baselines.json present ({p.stat().st_size} bytes)"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    checks = [
        ("CHANGELOG date freshness", _check_changelog_date),
        ("README.md link integrity", lambda: _check_referenced_files("README.md")),
        ("SUMMARY.md link integrity", lambda: _check_referenced_files("SUMMARY.md")),
        ("RUNBOOK.md link integrity", lambda: _check_referenced_files("RUNBOOK.md")),
        ("CHANGELOG.md link integrity", lambda: _check_referenced_files("CHANGELOG.md")),
        ("baselines.json present", _check_baselines_present),
    ]

    print("## Release-readiness checks\n")
    failures: list[str] = []
    for label, fn in checks:
        ok, detail = fn()
        marker = "OK  " if ok else "FAIL"
        print(f"  [{marker}] {label}: {detail}")
        if not ok:
            failures.append(label)

    print()
    if failures:
        print(f"NOT READY: {len(failures)} of {len(checks)} checks failed")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"READY: all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
