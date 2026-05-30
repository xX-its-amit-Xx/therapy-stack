#!/usr/bin/env python3
"""Pre-flight: run every static check + smoke before launching a bench.

A long bench run (~100 min on R1-Distill local) is expensive. Failing
mid-run on a curator typo or a leaky YAML wastes that time. This
script runs all the cheap checks first and reports green/red.

Checks:
  1. pytest tests/ -- unit tests for scoring helpers
  2. benchmark_lint.py -- YAML schema + leakage
  3. baselines compute (sandbox/run_blinded.py --baselines-only --set all)
  4. dataset_diversity.py -- generate fresh DIVERSITY.md

Exit code is the worst-case exit code of any sub-check. Designed to
be the one-line gate a developer runs before kicking off a bench:

    python scripts/preflight.py && \
        cd sandbox && python run_blinded.py --set val --out val.json

Each step prints its summary; on failure, look at the failing step's
output and re-run it directly for detail.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    """Run a subprocess, stream output, return exit code."""
    print(f"\n--- $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd or _ROOT)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=str(_ROOT / "sandbox" / ".venv" /
                                             "Scripts" / "python.exe"),
                    help="Python interpreter (default: sandbox venv).")
    ap.add_argument("--skip-baselines", action="store_true",
                    help="Skip the baselines-only run (faster but loses one check).")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    py = args.python
    print(f"Pre-flight with python={py}")

    checks = [
        ("Unit tests",         [py, "-m", "pytest", "tests/", "-q"]),
        ("Benchmark YAML lint", [py, "scripts/benchmark_lint.py"]),
        ("Dataset diversity",   [py, "scripts/dataset_diversity.py"]),
    ]
    if not args.skip_baselines:
        checks.append((
            "Baselines compute",
            [py, "sandbox/run_blinded.py", "--baselines-only", "--set", "all"],
        ))

    failures: list[str] = []
    for label, cmd in checks:
        # Some commands need to run from sandbox/ to find the agent imports.
        if cmd[1] == "sandbox/run_blinded.py":
            cmd2 = [py, "run_blinded.py"] + cmd[2:]
            rc = _run(cmd2, cwd=_ROOT / "sandbox")
        else:
            rc = _run(cmd, cwd=_ROOT)
        if rc != 0:
            failures.append(label)
            print(f"  FAIL: {label} (exit {rc})")
        else:
            print(f"  OK: {label}")

    print()
    if failures:
        print(f"PRE-FLIGHT FAIL: {len(failures)} of {len(checks)} checks failed")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PRE-FLIGHT OK: all {len(checks)} checks passed; safe to launch bench")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
