#!/usr/bin/env python3
"""Regression check: compare a fresh benchmark run against the baselines
lockfile and fail loudly if recovery dropped beyond the configured tolerance.

Designed to be called from CI:

    python scripts/regression_check.py \
        --dev sandbox/dev_results.json \
        --val sandbox/val_results.json \
        --baseline baselines.json

The baselines lockfile is checked into the repo and updated only by an
explicit PR with reviewer sign-off. This is how production teams catch
silent regressions introduced by prompt or retrieval changes.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=Path, required=True,
                    help="Path to fresh dev_results.json from run_blinded.py")
    ap.add_argument("--val", type=Path, required=True,
                    help="Path to fresh val_results.json from run_blinded.py")
    ap.add_argument("--baseline", type=Path, required=True,
                    help="Path to baselines.json (the lockfile)")
    ap.add_argument("--tolerance", type=int, default=1,
                    help="How many cases worse than baseline before failing (default 1)")
    args = ap.parse_args()

    if not args.dev.exists():
        print(f"FAIL: dev results not found at {args.dev}", file=sys.stderr); return 2
    if not args.val.exists():
        print(f"FAIL: val results not found at {args.val}", file=sys.stderr); return 2
    if not args.baseline.exists():
        print(f"WARN: baseline lockfile not found at {args.baseline}; nothing to compare. "
              "Treating as first run; not failing.")
        return 0

    base = _load(args.baseline)
    dev = _load(args.dev)
    val = _load(args.val)

    failures: list[str] = []

    # ── target recovery ──────────────────────────────────────────────────────
    for split, fresh in (("dev", dev), ("val", val)):
        n = fresh["n_cases"]
        hits = fresh["target_recovered"]
        prior = base.get(split, {}).get("target_recovered")
        if prior is None:
            print(f"INFO: no prior {split} baseline; recording fresh {hits}/{n}")
            continue
        if hits + args.tolerance < prior:
            failures.append(
                f"REGRESSION on {split}: target {hits}/{n} vs baseline {prior}/{n} "
                f"(tolerance = -{args.tolerance})"
            )
        else:
            sign = "+" if hits >= prior else ""
            print(f"OK {split}: target {hits}/{n} (delta {sign}{hits - prior} vs {prior})")

    # ── hard / easy splits ──────────────────────────────────────────────────
    HARD = {"brd4780_umod","ekterly_serping1","obesity_pomc","porphyria_alas1","sma_smn1",
            "pnh_piga","migraine_cgrp","ra_tnf",
            # post-2024 hard cases:
            "sotatercept_pah","crinecerfont_cah","garadacimab_hae"}
    for split, fresh in (("dev", dev), ("val", val)):
        hard_hits = sum(1 for r in fresh["results"]
                        if r["case_id"] in HARD and r.get("target_recovered"))
        hard_n = sum(1 for r in fresh["results"] if r["case_id"] in HARD)
        prior = base.get(split, {}).get("hard_recovered")
        if prior is None or hard_n == 0:
            continue
        if hard_hits + args.tolerance < prior:
            failures.append(
                f"REGRESSION on {split}/hard: {hard_hits}/{hard_n} vs baseline {prior}"
            )
        else:
            print(f"OK {split}/hard: {hard_hits}/{hard_n} (baseline {prior})")

    # ── cost ceiling ────────────────────────────────────────────────────────
    for split, fresh in (("dev", dev), ("val", val)):
        wall = fresh.get("total_seconds", 0)
        prior_wall = base.get(split, {}).get("total_seconds_max")
        if prior_wall and wall > prior_wall * 1.25:
            failures.append(
                f"COST REGRESSION on {split}: wall {wall:.0f}s vs baseline ceiling {prior_wall:.0f}s "
                "(>25% slower)"
            )

    if failures:
        print()
        print("=" * 60)
        print("REGRESSION CHECK FAILED")
        print("=" * 60)
        for f in failures:
            print("  - " + f)
        print()
        print("If this is intentional, update baselines.json in the same PR.")
        return 1

    print("\nRegression check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
