#!/usr/bin/env python3
"""Pattern-conditional recovery rate.

For each Stage-1 pattern_id, what fraction of cases where the agent
picked that pattern actually recovered the FDA-approved target?

This isolates which patterns the agent is GOOD at (e.g. pattern 1
downstream_effector on HAE-class cases) and which are LOAD-BEARING
but error-prone (e.g. pattern 9 feedback_axis_receptor where Stage 2
disambiguation is hard).

Use this to drive prompt optimization: invest more time on the
pattern with the lowest recovery rate (typically the highest-stakes
patterns get the worst hit rate -- selection effect).

Usage:
    python scripts/pattern_recovery_rate.py sandbox/blinded_*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


_PATTERN_LABEL = {
    "1":  "downstream_effector",
    "2":  "paralog",
    "3":  "upstream_enzyme",
    "4a": "disease_gene_chaperone",
    "4b": "cargo_receptor",
    "5":  "disease_gene_mRNA",
    "6":  "downstream_receptor_agonist",
    "7":  "disease_gene_exon_skip",
    "8":  "repressor",
    "9":  "feedback_axis_receptor",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    # Aggregate across all input runs.
    pattern_total = defaultdict(int)
    pattern_hits = defaultdict(int)
    case_count = 0
    for p in args.paths:
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in d.get("results", []):
            pid = r.get("strategy_pattern_id") or ""
            if not pid:
                continue
            pattern_total[pid] += 1
            if r.get("target_recovered"):
                pattern_hits[pid] += 1
            case_count += 1

    if case_count == 0:
        print("No cases with strategy_pattern_id found "
              "(runs predate v0.9.1?)")
        return 1

    print(f"# Pattern-conditional recovery ({case_count} cases across "
          f"{len(args.paths)} runs)\n")
    print("| Pattern | Label | Picks | Recovered | Pct |")
    print("|---|---|---|---|---|")
    for pid in sorted(pattern_total, key=lambda k: -pattern_total[k]):
        label = _PATTERN_LABEL.get(pid, "(unknown)")
        n = pattern_total[pid]
        h = pattern_hits[pid]
        print(f"| `{pid}` | {label} | {n} | {h} | {h/n*100:.0f}% |")

    # Surface the highest-stakes low-recovery pattern.
    worst = min(((pid, pattern_total[pid], pattern_hits[pid])
                  for pid in pattern_total if pattern_total[pid] >= 2),
                 key=lambda kv: kv[2]/kv[1], default=None)
    if worst:
        pid, n, h = worst
        if h / n < 0.5:
            print()
            print(f"> ⚠ Lowest-recovery pattern: `{pid}` "
                  f"({_PATTERN_LABEL.get(pid, '?')}) at {h/n*100:.0f}% "
                  f"({h}/{n}). Targets for the next prompt iteration.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
