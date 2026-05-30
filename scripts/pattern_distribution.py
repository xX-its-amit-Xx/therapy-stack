#!/usr/bin/env python3
"""Stage-1 pattern distribution analysis across a benchmark run.

The strategy_synthesis pipeline has 9 mechanism-to-strategy patterns:

  1. downstream_effector       (LoF inhibitor -> unbraked effector)
  2. paralog                    (silent paralog augmentation)
  3. upstream_enzyme            (toxic substrate buildup)
  4a. disease_gene_protein_chaperone (misfolding refold)
  4b. cargo_receptor            (ER-retention redirect)
  5. disease_gene_mRNA          (knock down GOF mRNA)
  6. downstream_receptor_agonist (hormone-deficiency bypass)
  7. disease_gene_exon_skip     (splice-modulating ASO)
  8. repressor                  (paralog reactivation)
  9. feedback_axis_receptor     (compensatory upstream blockade; v0.9.1)

If the agent picks pattern 4a (chaperone) for 80% of cases, that's a
*Stage-1 collapse*: the LLM is anchoring on one archetype regardless
of biology. Surfacing this helps catch prompt regressions BEFORE the
headline target-recovery number moves.

Usage:
    python scripts/pattern_distribution.py sandbox/blinded_*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


# Display labels for the 9 patterns.
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


def _summarize(run: dict) -> dict:
    results = run.get("results") or []
    patterns = Counter()
    hits_by_pattern = Counter()
    for r in results:
        pid = r.get("strategy_pattern_id") or "?"
        patterns[pid] += 1
        if r.get("target_recovered"):
            hits_by_pattern[pid] += 1
    return {
        "n": len(results),
        "patterns": dict(patterns),
        "hits_by_pattern": dict(hits_by_pattern),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    for p in args.paths:
        if not p.exists():
            print(f"SKIP {p}: not found")
            continue
        try:
            run = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"SKIP {p}: parse failed ({e})")
            continue
        s = _summarize(run)
        if s["n"] == 0:
            continue
        print(f"## {p.name} (N={s['n']})\n")
        if not s["patterns"] or "?" in s["patterns"] and len(s["patterns"]) == 1:
            print("> No `strategy_pattern_id` field in results (run predates v0.9.1).\n")
            continue
        print("| Pattern | Label | Picks | Recovery within pattern |")
        print("|---|---|---|---|")
        for pid, n in sorted(s["patterns"].items(), key=lambda kv: -kv[1]):
            hits = s["hits_by_pattern"].get(pid, 0)
            label = _PATTERN_LABEL.get(pid, "(unknown)")
            print(f"| `{pid}` | {label} | {n} ({n/s['n']*100:.0f}%) | "
                  f"{hits}/{n} ({hits/n*100:.0f}%) |")
        print()

        # Surface concentration: if any single pattern dominates >60%,
        # flag as a possible Stage-1 collapse.
        top_pid, top_n = max(s["patterns"].items(), key=lambda kv: kv[1])
        if top_n / s["n"] > 0.6 and top_pid != "?":
            print(f"> ⚠ Stage-1 concentration: pattern `{top_pid}` "
                  f"({_PATTERN_LABEL.get(top_pid, '?')}) picked "
                  f"{top_n/s['n']*100:.0f}% of cases. Investigate whether "
                  f"the dataset really has that bias, or whether the "
                  f"selector is anchoring.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
