#!/usr/bin/env python3
"""Pre-commit check: don't accidentally modify a val case.

`val/` is the held-out split. Editing one in response to a failed run
silently invalidates the generalization claim. This script checks
`git diff --name-only` against `main` and fails if any
benchmarks/heldout_2024_2025/*.yaml is in the diff.

Override with `--allow-val-edit "REASON"` if the edit is intentional
(e.g. quarterly rotation -- see RUNBOOK section 8).

Usage:
    python scripts/val_integrity_check.py
    python scripts/val_integrity_check.py --allow-val-edit "Q2 rotation"

Designed to run in CI on PRs targeting main. Exits 1 if a val case
is touched without --allow-val-edit.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def _changed_files_vs_main() -> list[str]:
    """Files changed in the current branch vs main."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "main...HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=5)
        return [f.strip() for f in out.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        # Maybe no main branch ref; fall back to staged + unstaged.
        try:
            out = subprocess.check_output(
                ["git", "diff", "--name-only", "HEAD"],
                text=True, stderr=subprocess.DEVNULL, timeout=5)
            return [f.strip() for f in out.splitlines() if f.strip()]
        except Exception:
            return []
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-val-edit", default="",
                    help="Reason for editing val (required if val touched).")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    files = _changed_files_vs_main()
    val_pattern = "benchmarks/heldout_2024_2025/"
    val_touched = [f for f in files if val_pattern in f]

    if not val_touched:
        print(f"OK: no val cases touched ({len(files)} files in diff)")
        return 0

    if args.allow_val_edit:
        print(f"OK: {len(val_touched)} val case(s) touched, but "
              f"explicitly allowed with reason: {args.allow_val_edit!r}")
        for f in val_touched:
            print(f"  - {f}")
        return 0

    print(f"FAIL: {len(val_touched)} val case(s) touched without "
          f"--allow-val-edit:")
    for f in val_touched:
        print(f"  - {f}")
    print()
    print("If this is a legitimate quarterly rotation (see RUNBOOK "
          "section 8), re-run with --allow-val-edit \"<reason>\".")
    print("Otherwise: revert the val edits. Touching val in response "
          "to a result invalidates the held-out claim.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
