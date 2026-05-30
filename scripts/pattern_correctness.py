#!/usr/bin/env python3
"""Pattern-correctness analysis: did Stage 1 pick the right pattern?

For each case, infer the "expected" pattern_id from the relationship
between expected_target and disease_gene, then compare to the
agent's strategy_pattern_id.

Inference rules:
  - expected_target == disease_gene  → pattern is 4a, 5, or 7 (one of
    the disease-gene-centric patterns). We can't disambiguate further
    from the YAML alone without curator input, but we can flag any
    NON-disease-gene-centric pick as wrong.
  - expected_target != disease_gene  → pattern is 1, 2, 3, 4b, 6, 8,
    or 9. Use heuristics on the target name to narrow:
      * "...RHR" or "GnRHR" or "TRHR" → 9 (feedback axis)
      * paralog-shaped (same root as disease gene) → 2 or 8
      * everything else → 1 (downstream_effector)

Output reports per-case:
  - case_id
  - expected pattern (inferred)
  - picked pattern (from strategy_pattern_id)
  - agreement
  - whether this is a Stage-1 error or a Stage-2 error if missed

This is a coarse signal -- the inference isn't perfect -- but it
gives a single bit of debugging info per case: "did we fail at the
pattern level or the within-pattern picker level?"

Usage:
    python scripts/pattern_correctness.py sandbox/blinded_*.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _canon(t: str) -> str:
    if not t:
        return ""
    m = re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", t)
    return (m.group(0) if m else t.strip()).upper()


_FEEDBACK_RECEPTOR_SUFFIXES = ("RHR1", "RHR2", "GNRHR", "TRHR", "GHRHR")


def _expected_pattern(gene: str, target: str) -> str:
    """Best-effort inference of which of the 9 patterns the expected
    target reflects. Returns '?' if unsure."""
    g = _canon(gene)
    t = _canon(target)
    if not g or not t:
        return "?"
    if g == t:
        # Disease-gene-centric. Without more YAML hints, default to '5'
        # (mRNA knockdown) for ASOs / siRNAs. The score doesn't really
        # depend on disambiguating 4a/5/7 here -- they all have
        # disease_gene_* target_kind.
        return "5/4a/7"
    # Feedback-axis: target ends with a releasing-hormone-receptor suffix.
    if any(t.endswith(sfx) for sfx in _FEEDBACK_RECEPTOR_SUFFIXES):
        return "9"
    # Paralog: same root letters as disease gene, different digits.
    g_root = re.sub(r"\d+$", "", g)
    t_root = re.sub(r"\d+$", "", t)
    if g_root and g_root == t_root and g != t:
        return "2/8"
    # Default: downstream effector.
    return "1/3/6"


def _expected_kind(gene: str, target: str) -> str:
    """Coarser bucket: 'disease_gene' / 'non_disease_gene'."""
    g = _canon(gene)
    t = _canon(target)
    if not g or not t:
        return "?"
    return "disease_gene" if g == t else "non_disease_gene"


_DISEASE_GENE_KINDS = {
    "disease_gene_protein_chaperone",
    "disease_gene_mRNA",
    "disease_gene_exon_skip",
}


def _picked_kind(picked_target_kind: str) -> str:
    if not picked_target_kind:
        return "?"
    return "disease_gene" if picked_target_kind in _DISEASE_GENE_KINDS \
        else "non_disease_gene"


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
        if not results:
            continue
        print(f"## {p.name}\n")
        print("| Case | Expected pattern | Picked pattern_id | Agreement | Verdict |")
        print("|---|---|---|---|---|")
        stage1_errors = 0
        stage2_errors = 0
        for r in results:
            cid = r.get("case_id", "?")
            exp_pat = _expected_pattern(r.get("gene", ""), r.get("expected_target", ""))
            picked = r.get("strategy_pattern_id", "")
            exp_kind = _expected_kind(r.get("gene", ""),
                                       r.get("expected_target", ""))
            picked_kind = _picked_kind(r.get("strategy_target_kind", ""))
            recovered = bool(r.get("target_recovered"))
            kind_agreement = exp_kind == picked_kind
            verdict = "—"
            if not recovered:
                if not kind_agreement and exp_kind != "?":
                    verdict = "Stage-1 error (wrong pattern kind)"
                    stage1_errors += 1
                else:
                    verdict = "Stage-2 error (right pattern, wrong target)"
                    stage2_errors += 1
            agreement = "✓" if (exp_pat == picked or
                                 picked in exp_pat.split("/")) else "✗"
            print(f"| `{cid}` | {exp_pat} | `{picked or '?'}` | {agreement} | {verdict} |")

        miss_count = sum(1 for r in results if not r.get("target_recovered"))
        if miss_count:
            print()
            print(f"### Miss breakdown")
            print(f"- Stage-1 (wrong pattern kind): {stage1_errors}")
            print(f"- Stage-2 (right pattern, wrong specific target): {stage2_errors}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
