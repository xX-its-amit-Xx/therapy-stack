#!/usr/bin/env python3
"""Cross-run agreement: given N result JSONs, show per-case agreement.

The bench is non-deterministic (LLM temperature, occasional tool
failures, retrieval cache misses). Running it twice and comparing
recovery numbers obscures that: 9/12 vs 9/12 looks like agreement
even if 3 cases flipped in opposite directions.

This script reports:
  - per-case: which target each run predicted
  - case-level agreement %: how many cases have the same prediction
    across all runs
  - flip rate: how many cases changed predictions between any two runs
  - stable hits: cases recovered in every run
  - flaky cases: cases that recovered in one run but not another

Designed to be run on 2-3 replicates of the SAME pipeline against the
SAME split. Use --label to give each run a short tag.

Usage:
    python scripts/cross_run_agreement.py \\
        --label r1 sandbox/blinded_v20_val_llama.json \\
        --label r2 sandbox/blinded_v20b_val_llama.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


def _canon(t: str) -> str:
    if not t:
        return ""
    m = re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", t)
    return (m.group(0) if m else t.strip()).upper()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--label", action="append", default=None,
                    help="Per-run label; pass once per --label. Defaults to filename stem.")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if not args.paths:
        return 1
    if args.label and len(args.label) != len(args.paths):
        print("FAIL: number of --label flags must equal number of paths")
        return 1
    labels = args.label or [p.stem for p in args.paths]

    runs = []
    for p in args.paths:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"SKIP {p}: {e}")
            return 1
        runs.append({r["case_id"]: r for r in d.get("results", [])})

    # Union of case_ids across all runs.
    all_cases = set()
    for r in runs:
        all_cases |= set(r.keys())
    cases = sorted(all_cases)

    print(f"# Cross-run agreement -- {len(runs)} runs, {len(cases)} cases\n")

    # Per-case row table.
    print("| Case | " + " | ".join(labels) + " | Agreement | Recovered |")
    print("|---|" + "|".join(["---"] * (len(labels) + 2)) + "|")

    flip_count = 0
    stable_hits = 0
    flaky_cases = []
    full_agreement = 0
    for cid in cases:
        preds = []
        recovered = []
        for r in runs:
            c = r.get(cid)
            if c is None:
                preds.append("(missing)")
                recovered.append(False)
                continue
            preds.append(_canon(c.get("predicted_target") or "") or "?")
            recovered.append(bool(c.get("target_recovered")))
        agree = len(set(preds)) == 1
        if agree:
            full_agreement += 1
        else:
            flip_count += 1
        if all(recovered):
            stable_hits += 1
        elif any(recovered) and not all(recovered):
            flaky_cases.append(cid)
        rec_str = "/".join("Y" if x else "n" for x in recovered)
        agree_str = "all same" if agree else "DIFFER"
        print(f"| `{cid}` | " + " | ".join(f"`{p}`" for p in preds) +
              f" | {agree_str} | {rec_str} |")

    print()
    print("## Summary\n")
    print(f"- Cases with identical predictions across all runs: "
          f"{full_agreement}/{len(cases)} ({full_agreement/max(len(cases),1)*100:.0f}%)")
    print(f"- Cases that flipped between runs: "
          f"{flip_count}/{len(cases)} ({flip_count/max(len(cases),1)*100:.0f}%)")
    print(f"- Cases recovered in EVERY run: {stable_hits}/{len(cases)}")
    if flaky_cases:
        print(f"- Flaky cases (some runs hit, some missed): "
              f"{len(flaky_cases)} -- {', '.join('`'+c+'`' for c in flaky_cases)}")
    print()
    print("> Flaky cases are the noise floor of the bench. Their count "
          "is what you compare a +1 case improvement against.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
