#!/usr/bin/env python3
"""Suggest the highest-leverage next change based on the miss profile.

Reads a result JSON, runs miss_taxonomy + pattern_correctness + dg-default
rate inline, and emits a prioritized action list:

  - If any case is `disease_gene_default` with target_kind in non-disease-
    gene kinds: the v0.9 guard isn't catching it -> check the guard set.
  - If feedback-axis phenotype + Stage-1 picked chaperone/mRNA/exon-skip:
    v0.9.2b override not firing -> check phenotype markers list.
  - If most misses are paralog_confusion: candidate set narrowing or
    family-disambiguation prompt rule.
  - If most misses are confabulation_off_pathway: retrieval is the
    bottleneck, not reasoning.
  - If misses are mostly Stage-2 (right pattern, wrong target): improve
    Stage-2 picker prompt for that target_kind.

Output is markdown with one recommendation per identified issue, in
priority order.

Usage:
    python scripts/next_action.py sandbox/blinded_v20_val_llama.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from miss_taxonomy import classify        # type: ignore[import]
from pattern_correctness import _expected_kind, _picked_kind   # type: ignore[import]


def _recommendations(results: list[dict]) -> list[str]:
    """Build a prioritized list of actionable recommendations."""
    recs: list[str] = []
    if not results:
        return ["No results in file."]

    misses = [r for r in results if not r.get("target_recovered")]
    if not misses:
        recs.append("All cases recovered. Consider expanding the test set "
                    "or running on the adversarial split.")
        return recs

    failure_counts = Counter(classify(m) for m in misses)
    n_misses = len(misses)

    # Stage-1 vs Stage-2 split.
    stage1_errors = 0
    stage2_errors = 0
    for m in misses:
        exp_kind = _expected_kind(m.get("gene", ""), m.get("expected_target", ""))
        picked_kind = _picked_kind(m.get("strategy_target_kind", ""))
        if exp_kind != "?" and picked_kind != "?" and exp_kind != picked_kind:
            stage1_errors += 1
        else:
            stage2_errors += 1

    # Priority 1: dominant disease_gene_default.
    if failure_counts.get("disease_gene_default", 0) >= n_misses * 0.5:
        recs.append(
            f"**Disease-gene-default dominates ({failure_counts['disease_gene_default']}/{n_misses}).** "
            "Check whether the v0.9.x guards fired. If `strategy_target_kind` "
            "is in the disease-gene-centric set on miss cases, the guard "
            "didn't catch them -- extend the override conditions. If kind "
            "is empty, Stage 1 LLM JSON parsing failed -- harden the parser."
        )

    # Priority 2: feedback-axis cases that missed.
    feedback_misses = [m for m in misses if any(
        k in (m.get("expected_target", "") or "").upper()
        for k in ("RHR1", "RHR2", "GNRHR", "TRHR"))]
    if feedback_misses:
        recs.append(
            f"**Feedback-axis cases missing ({len(feedback_misses)}).** "
            "If pattern_id is 9 but target is wrong (NR3C1 instead of CRHR1), "
            "the Stage-2 picker prompt rule for feedback_axis_receptor needs "
            "more specificity. v0.9.4 added the basics; consider a stricter "
            "candidate-set filter that excludes end-hormone receptors."
        )

    # Priority 3: paralog confusion.
    if failure_counts.get("paralog_confusion", 0) >= 1:
        recs.append(
            f"**Paralog confusion ({failure_counts['paralog_confusion']} case(s)).** "
            "The agent is hitting biology-class siblings (e.g. CHRM5 vs CHRM4). "
            "Either (a) broaden the YAML's valid_targets if the sibling is "
            "biologically defensible, or (b) strengthen the picker's "
            "family-disambiguation prompt with explicit \"do not pick a "
            "sibling unless it's in the candidate set\"."
        )

    # Priority 4: confabulation = retrieval bottleneck.
    if failure_counts.get("confabulation_off_pathway", 0) >= 1:
        recs.append(
            f"**Confabulation off-pathway ({failure_counts['confabulation_off_pathway']} case(s)).** "
            "The candidate set didn't contain the right answer. Check "
            "pathway_genes for these cases -- likely needs an additional "
            "agentic_target_research tool call (pathway_neighbors, "
            "find_signaling_family) or a wider Reactome lookup."
        )

    # Priority 5: Stage-2 errors.
    if stage2_errors >= n_misses * 0.5:
        recs.append(
            f"**Stage-2 errors dominate ({stage2_errors}/{n_misses}).** "
            "Pattern is right but picker chooses wrong specific gene. "
            "This is the hardest miss class -- LLM prior beats prompt rule. "
            "Consider a structural fix (constrain candidate set) or a "
            "larger model."
        )

    return recs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    d = json.loads(args.path.read_text(encoding="utf-8"))
    results = d.get("results", [])

    print(f"# Next-action recommendations -- {args.path.name}\n")
    n = len(results)
    hits = sum(1 for r in results if r.get("target_recovered"))
    print(f"Run summary: {hits}/{n} cases recovered. "
          f"DG-default rate: "
          f"{d.get('disease_gene_default_rate', 0)*100:.0f}%\n")

    recs = _recommendations(results)
    for i, rec in enumerate(recs, 1):
        print(f"{i}. {rec}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
