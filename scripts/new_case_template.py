#!/usr/bin/env python3
"""Scaffold a new YAML benchmark case from minimal inputs.

Lowers the friction to add a val case from a current FDA approval.
Given a gene and an approximate disease description, emit a starter
YAML with the right schema (id, name, category, input, expected_outputs)
ready for the curator to fill in the specifics.

The curator still has to:
  - Write the mutation text from real ClinVar / OMIM data
  - Name the expected target_protein
  - Fill in target_aliases (include both HGNC and drug-relevant names)
  - Add valid_targets if multi-target acceptance applies
  - Provide key_citations (drug name, brand name, trial acronym)
  - Add references (NEJM / Lancet / FDA letter)

The scaffold ensures every required field is present and pre-fills
sensible defaults where possible.

Usage:
    python scripts/new_case_template.py --gene FGFR2 --disease "achondroplasia" \
        --category heldout_2024 --out benchmarks/heldout_2024_2025/_new.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


_TEMPLATE = """id: {id}
name: "{disease_short} -> [DRUG] ([TARGET-FAMILY] [MODULATOR-CLASS])"
category: {category}
approval_date: "{approval_date}"
fda_approval: "[BRAND] ([generic]) -- one-line FDA approval summary"

input:
  gene: "{gene}"
  mutation: "[TODO: pull from ClinVar/OMIM; e.g. 'heterozygous gain-of-function p.GLY380ARG']"
  disease_phenotype: "[TODO: describe phenotype; include feedback markers like 'ACTH-driven' or 'compensatory' if applicable]"

expected_outputs:
  target_protein: "[TARGET HGNC symbol or 'GENE (mRNA)']"
  target_aliases: ["[HGNC]", "[protein name]", "[generic drug name]", "[brand name]"]
  # Add valid_targets ONLY if multiple FDA targets are biologically defensible
  # for the same disease. Single-target cases should OMIT this field.
  # valid_targets: ["TARGET1", "TARGET2"]
  modulation_type: "[inhibitor | activator | siRNA_ASO | chaperone | gene_therapy | splice_modifier]"
  key_citations:
    - "[generic drug name]"
    - "[brand name]"
    - "[trial acronym]"
  mechanism_class: "[lof | gof | dominant_negative | aggregation]"
  min_confidence: 0.65

references:
  - "[NEJM / Lancet citation]"
  - "[FDA approval letter, NDA/BLA number]"
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gene", required=True,
                    help="HGNC symbol of the disease gene")
    ap.add_argument("--disease", required=True,
                    help="Short disease description (becomes part of name)")
    ap.add_argument("--id", default=None,
                    help="Case id slug; defaults to <drug>_<gene_lower>")
    ap.add_argument("--category", default="heldout_2024",
                    choices=["curated", "heldout_2024", "adversarial",
                              "primary", "canonical_oncology",
                              "canonical_neurology", "canonical_complement",
                              "canonical_immunology"],
                    help="YAML category field (heldout_2024 for val)")
    ap.add_argument("--approval-date", default="YYYY-MM-DD",
                    help="FDA approval date (YYYY-MM-DD)")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output YAML path")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    case_id = args.id or f"NEW_{args.gene.lower()}"
    text = _TEMPLATE.format(
        id=case_id,
        gene=args.gene.upper(),
        disease_short=args.disease,
        category=args.category,
        approval_date=args.approval_date,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote scaffold to {args.out}")
    print(f"Next: fill in the TODOs, then run `python scripts/benchmark_lint.py` "
          f"to validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
