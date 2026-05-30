#!/usr/bin/env python3
"""CI gate: detect Stage-1 pattern collapse across a benchmark run.

Pattern collapse is the failure mode where Stage 1 anchors on a
single pattern (e.g. 4a chaperone) for >K% of cases regardless of
biology -- a symptom of LLM regression that shows up BEFORE the
headline target-recovery number moves.

This script reads a `blinded_*.json`, looks at the
`strategy_pattern_id` field on each case, and exits 1 if:
  - any single pattern represents > --max-share (default 60%)
    of all cases
  - OR fewer than --min-distinct (default 3) distinct patterns
    were picked across the run

Both bounds are loose enough that healthy v0.9 runs pass but the
collapsed-to-pattern-4a degenerate runs fail.

Usage:
    python scripts/pattern_collapse_check.py sandbox/blinded_v20_val_llama.json
    python scripts/pattern_collapse_check.py --max-share 0.5 --min-distinct 4 sandbox/...
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--max-share", type=float, default=0.6,
                    help="Fail if any one pattern > this share of cases.")
    ap.add_argument("--min-distinct", type=int, default=3,
                    help="Fail if fewer than this many distinct patterns picked.")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    d = json.loads(args.path.read_text(encoding="utf-8"))
    results = d.get("results", [])
    n = len(results)
    if n == 0:
        print(f"FAIL: {args.path.name} has no results")
        return 1

    pids = [r.get("strategy_pattern_id") or "" for r in results]
    valid = [p for p in pids if p]
    if not valid:
        # Run predates v0.9.1; nothing to gate on. Pass silently.
        print(f"SKIP: {args.path.name} has no strategy_pattern_id "
              f"(run predates v0.9.1)")
        return 0

    counts = Counter(valid)
    top_pid, top_n = counts.most_common(1)[0]
    top_share = top_n / n
    n_distinct = len(counts)

    print(f"Pattern distribution across {n} cases:")
    for pid, k in counts.most_common():
        print(f"  pattern_{pid}: {k}/{n} ({k/n*100:.0f}%)")

    failed = False
    if top_share > args.max_share:
        print(f"\nFAIL: pattern_{top_pid} dominates "
              f"{top_share*100:.0f}% > {args.max_share*100:.0f}% threshold")
        failed = True
    if n_distinct < args.min_distinct:
        print(f"\nFAIL: only {n_distinct} distinct patterns picked, "
              f"min is {args.min_distinct}")
        failed = True

    if not failed:
        print(f"\nOK: top pattern share {top_share*100:.0f}% "
              f"<= {args.max_share*100:.0f}%, "
              f"{n_distinct} distinct patterns >= {args.min_distinct}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
