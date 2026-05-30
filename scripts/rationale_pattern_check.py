#!/usr/bin/env python3
"""Static heuristic: does the predicted rationale match the picked pattern?

When the agent picks a pattern (say `feedback_axis_receptor`) but the
rationale says "this aligns with the chosen pattern of
'disease_gene_protein_chaperone'", that's a Stage-2 contradiction:
either the picker copied the wrong pattern name from earlier prompts,
or the pattern override didn't propagate. Both are real bugs.

This is a STATIC heuristic, no LLM. It looks for a substring in the
rationale that contradicts the stored strategy_pattern_id /
strategy_target_kind. Output is a list of contradiction cases.

Used as a debugging tool when a run looks suspicious; not a CI gate.

Usage:
    python scripts/rationale_pattern_check.py sandbox/blinded_*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Map target_kind -> phrases that, when found in rationale, indicate
# the rationale is describing that pattern.
_RATIONALE_PHRASES = {
    "disease_gene_protein_chaperone": [
        "chaperone", "refold", "stabilize the mutant",
    ],
    "disease_gene_mRNA": [
        "knock down the disease gene", "mrna knockdown",
        "ASO/siRNA", "antisense", "knockdown of the disease gene",
    ],
    "feedback_axis_receptor": [
        "feedback", "upstream signaling", "compensatory", "ACTH",
        "axis blockade", "CRH receptor",
    ],
    "downstream_effector": [
        "downstream effector", "unbraked", "the enzyme it normally inhibits",
    ],
    "paralog": [
        "paralog", "sibling gene", "isoform",
    ],
    "upstream_enzyme": [
        "upstream enzyme", "rate-limiting", "drain flux",
    ],
    "cargo_receptor": [
        "cargo receptor", "ER retention", "TMED",
    ],
    "downstream_receptor_agonist": [
        "agonize the receptor", "hormone replacement",
    ],
    "repressor": [
        "repressor", "reactivate the paralog",
    ],
}


def _contradicts(rationale: str, picked_kind: str) -> str:
    """Return a contradicting other-kind name if the rationale mentions
    another pattern's phrases more strongly than the picked one."""
    rl = (rationale or "").lower()
    picked_hits = sum(1 for p in _RATIONALE_PHRASES.get(picked_kind, [])
                      if p.lower() in rl)
    for other_kind, phrases in _RATIONALE_PHRASES.items():
        if other_kind == picked_kind:
            continue
        other_hits = sum(1 for p in phrases if p.lower() in rl)
        if other_hits > picked_hits and other_hits >= 2:
            return other_kind
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    for p in args.paths:
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        results = d.get("results", [])
        contradictions = []
        for r in results:
            kind = r.get("strategy_target_kind") or ""
            rat = r.get("predicted_rationale") or ""
            if not kind or not rat:
                continue
            other = _contradicts(rat, kind)
            if other:
                contradictions.append({
                    "case_id": r.get("case_id"),
                    "picked_kind": kind,
                    "rationale_implies": other,
                    "rationale": rat[:200],
                })
        print(f"## {p.name}: {len(contradictions)} rationale-vs-pattern contradictions")
        if not contradictions:
            continue
        for c in contradictions:
            print(f"- `{c['case_id']}`: picked={c['picked_kind']}, "
                  f"rationale says={c['rationale_implies']}")
            print(f"    {c['rationale']!r}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
