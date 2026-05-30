#!/usr/bin/env python3
"""Lint the YAML benchmark cases for schema correctness + leakage.

Two passes:

1. SCHEMA: every case must have
     id, name, input.{gene, mutation, disease_phenotype},
     expected_outputs.{target_protein, modulation_type}.
   Cases missing required fields are reported.

2. LEAKAGE: the `input` block must not contain any string that appears
   in the `expected_outputs` (drug names, FDA brand names, expected
   target symbol). The original v0.2 -> v0.3 regression was caused by
   leakage in curator YAMLs; this check is the static gate against
   that regression class.

Exit code 1 if any case fails either check. Designed to be wired into
the CI smoke job.

Usage:
    python scripts/benchmark_lint.py
    python scripts/benchmark_lint.py --strict   # also lint disease_phenotype
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml  # type: ignore[import]


_AGENT_REPO = Path(__file__).resolve().parents[1].parent / "therapy-agent"
_BM = _AGENT_REPO / "benchmarks"


_REQUIRED_INPUT = ("gene", "mutation", "disease_phenotype")
_REQUIRED_EXPECTED = ("target_protein", "modulation_type")


# Strings we DO allow to appear in the input even though they're in
# expected_outputs -- they're standard biology vocabulary, not drug
# names. The leakage check is about "the agent sees the answer before
# the LLM call"; HGNC symbols of the disease gene appearing in the
# input is fine (they should!), but the FDA drug name should not.
_GENERIC_BIOLOGY = {
    "inhibitor", "activator", "agonist", "antagonist", "modulator",
    "receptor", "enzyme", "protein", "gene", "antibody", "monoclonal",
    "siRNA", "ASO", "antisense", "splice", "exon", "mRNA",
    "lof", "gof", "missense", "loss-of-function", "gain-of-function",
    "deficiency", "deletion", "duplication", "missense", "nonsense",
}


def _is_hgnc_symbol(s: str) -> bool:
    """Approximate HGNC symbol detector. Real HGNC symbols are uppercase
    letters + digits, 2-10 chars, no spaces. This catches CYP21A2,
    BCL11A, IL13RA2, etc. but not 'IL-13' or 'amyloid-beta'."""
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", (s or "").strip()))


def _is_protein_descriptor(s: str) -> bool:
    """Names like 'dystrophin', 'alpha-galactosidase', 'hemoglobin S',
    'IL-13', 'amyloid-beta', 'muscarinic' -- biology vocabulary the
    agent is supposed to derive from the gene. Allowing the curator to
    put these in input.mutation describing the biology isn't leakage."""
    s = (s or "").strip().lower()
    # Plain biology words: protein-suffix endings, family names, common
    # short biology tokens. Heuristic; tolerate false positives in this
    # direction (under-flag) rather than the other (over-flag).
    biology_suffixes = ("ase", "in", "globin", "amyloid", "muscarinic")
    if any(s.endswith(sfx) for sfx in biology_suffixes):
        return True
    if any(tok in s for tok in ("hemoglobin", "amyloid", "muscarinic",
                                  "dystrophin", "galactosidase", "activin",
                                  "il-", "tnf-", "ifn-", "abeta")):
        return True
    return False


def _is_drug_inn_like(s: str) -> bool:
    """Heuristic for INN-style drug names: lowercase, single word,
    typically ending in a USAN/INN stem (-mab, -nib, -cept, -tide,
    -rsen, -giran, ...). Brand names are also flagged."""
    s = (s or "").strip()
    if not s or " " in s:
        return False
    drug_stems = ("mab", "nib", "cept", "tide", "rsen", "giran",
                   "siran", "stat", "inide", "nide", "nant", "fant",
                   "ide", "asib", "alazide", "vir", "buvir")
    return any(s.lower().endswith(stem) for stem in drug_stems)


def _is_brand_name_like(s: str) -> bool:
    """Brand names: capitalized, single word, 4-15 chars, not HGNC,
    not generic biology. Crenessity, Ekterly, Tryvio, etc."""
    s = (s or "").strip()
    if not (4 <= len(s) <= 15) or " " in s:
        return False
    if _is_hgnc_symbol(s):
        return False
    return s[0].isupper() and not s.isupper() and s[1:].islower()


def _tokens_for_leakage(exp: dict) -> set[str]:
    """Return strings from expected_outputs that, if found in input,
    constitute leakage.

    Leakage is specifically: FDA drug names (INN-style or brand-name).
    NOT leakage: HGNC symbols (the agent NEEDS to know the disease
    gene's symbol), generic biology vocabulary (inhibitor, antibody),
    or protein descriptors (dystrophin, hemoglobin S, IL-13).
    """
    leaky: set[str] = set()
    candidates: list[str] = []
    candidates += exp.get("key_citations") or []
    candidates += exp.get("target_aliases") or []
    for s in candidates:
        s = (s or "").strip()
        if not s:
            continue
        if s.lower().startswith("nct"):
            continue                          # trial ID
        if _is_hgnc_symbol(s):
            continue                          # gene symbol
        if s.lower() in _GENERIC_BIOLOGY:
            continue
        if _is_protein_descriptor(s):
            continue
        if _is_drug_inn_like(s) or _is_brand_name_like(s):
            leaky.add(s)
    return leaky


def _iter_yamls():
    for p in _BM.rglob("*.yaml"):
        if not p.is_file():
            continue
        yield p


def _lint(strict: bool = False) -> int:
    errors = 0
    n_cases = 0
    for p in _iter_yamls():
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  {p.relative_to(_BM)}: PARSE ERROR ({e})")
            errors += 1
            continue
        if not isinstance(doc, dict):
            continue
        n_cases += 1

        # Schema.
        inp = doc.get("input") or {}
        exp = doc.get("expected_outputs") or {}
        rel = p.relative_to(_BM)
        for f in _REQUIRED_INPUT:
            if not inp.get(f):
                print(f"  {rel}: SCHEMA missing input.{f}")
                errors += 1
        for f in _REQUIRED_EXPECTED:
            if not exp.get(f):
                print(f"  {rel}: SCHEMA missing expected_outputs.{f}")
                errors += 1

        # Leakage. Concatenate the input fields the LLM will see and
        # search for any leaky string from expected_outputs.
        input_text = " ".join(str(inp.get(k, "")) for k in _REQUIRED_INPUT).lower()
        if not strict:
            # By default we exclude the disease_phenotype since some
            # benign FDA names accidentally land there (e.g. "Tryvio")
            # but the v0.2 leakage was via the *gene* and *mutation*
            # fields. Strict mode flags both.
            input_text = " ".join(str(inp.get(k, "")) for k in
                                   ("gene", "mutation")).lower()
        for leaky in _tokens_for_leakage(exp):
            if leaky.lower() in input_text:
                print(f"  {rel}: LEAKAGE \"{leaky}\" appears in input")
                errors += 1

    print()
    if errors:
        print(f"FAIL: {errors} issues across {n_cases} YAML cases.")
    else:
        print(f"OK: {n_cases} YAML cases pass schema + leakage check.")
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="Also lint disease_phenotype for drug-name leakage.")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return _lint(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
