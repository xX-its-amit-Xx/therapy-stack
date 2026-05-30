"""Tests for the scoring helpers in sandbox/run_blinded.py.

These run without any LLM calls. They lock in the semantics of:
  - multi-target acceptance (valid_targets)
  - alias bag matching with the generic-alias filter
  - HGNC symbol intersection with the non-HGNC blocklist
  - modality crosswalk
  - citation matching
  - Wilson 95% CI

Run with: pytest tests/

If a future change moves any number reported in the README, one of
these tests should also move. If a future change moves a README number
WITHOUT moving a test, that's a yellow flag -- either the test is
stale or the number is.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sandbox/run_blinded.py importable.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "sandbox"))

# These imports require sandbox/.venv NOT to be active (top-level python).
# Tests will fail if you run them from inside the sandbox venv -- that's fine,
# they're meant to be run as `pytest tests/` from the repo root.
from run_blinded import (  # type: ignore[import]
    score_target,
    score_modality,
    score_citation,
    wilson_ci,
    _symbols,
    _is_generic_alias,
)


# ── score_target ──────────────────────────────────────────────────────────────

def test_target_primary_substring_match():
    exp = {"target_protein": "PCSK9", "target_aliases": [], "valid_targets": []}
    r = score_target("PCSK9 (mRNA)", exp)
    assert r["recovered"]
    assert r["matched_via_kind"] == "primary"


def test_target_alias_match_not_generic():
    exp = {"target_protein": "CRHR1",
           "target_aliases": ["CRH receptor", "corticotropin-releasing hormone receptor 1"],
           "valid_targets": []}
    r = score_target("CRH receptor antagonist", exp)
    assert r["recovered"]
    assert r["matched_via_kind"] == "alias"


def test_target_alias_generic_rejected():
    # "gene therapy" alone is a strategy descriptor, not a target.
    exp = {"target_protein": "SMN2",
           "target_aliases": ["SMN2", "gene therapy"],
           "valid_targets": []}
    # If the model says "gene therapy for SMN1", the SMN1 substring isn't
    # in the alias bag (different gene); we should NOT match via "gene therapy".
    r = score_target("gene therapy for the SMN1 transgene", exp)
    assert not r["recovered"]


def test_target_valid_targets_multi_match():
    exp = {"target_protein": "HBB",
           "target_aliases": ["voxelotor"],
           "valid_targets": ["HBB", "BCL11A", "HBG1", "HBG2", "SELP"]}
    r = score_target("BCL11A erythroid enhancer", exp)
    assert r["recovered"]
    assert r["matched_via_kind"] == "valid_target"


def test_target_symbol_intersection():
    exp = {"target_protein": "P53779 (PCSK9) — proprotein convertase",
           "target_aliases": [],
           "valid_targets": []}
    # Predicted contains PCSK9 as a token; matches via symbol intersection.
    r = score_target("inhibit PCSK9 with siRNA", exp)
    assert r["recovered"]


def test_target_non_hgnc_blocklist_filtered():
    # AAV9 is in the expected target string (delivery vector) but should NOT
    # let a prediction of "AAV9 capsid engineering" match.
    exp = {"target_protein": "SMN1 locus (delivered via AAV9 capsid)",
           "target_aliases": [],
           "valid_targets": []}
    r = score_target("AAV9 capsid engineering", exp)
    # AAV9 is in _NON_HGNC_BLOCKLIST so symbol intersection should reject.
    # SMN1 not in pred. No match.
    assert not r["recovered"]


def test_target_no_prediction():
    exp = {"target_protein": "PCSK9", "target_aliases": [], "valid_targets": []}
    r = score_target("", exp)
    assert not r["recovered"]
    assert r["matched_via_kind"] is None


# ── score_modality ────────────────────────────────────────────────────────────

def test_modality_canonical_class_match():
    exp = {"modulation_type": "inhibitor"}
    assert score_modality("inhibitor", exp)
    assert score_modality("antagonist", exp)
    assert score_modality("anti-PCSK9", exp)


def test_modality_synonym_class_match():
    exp = {"modulation_type": "siRNA_ASO"}
    assert score_modality("antisense oligonucleotide", exp)
    assert score_modality("RNAi", exp)
    assert score_modality("siRNA", exp)


def test_modality_wrong_class_no_match():
    exp = {"modulation_type": "chaperone"}
    assert not score_modality("inhibitor", exp)


def test_modality_empty():
    exp = {"modulation_type": ""}
    assert not score_modality("", exp)
    assert not score_modality("inhibitor", exp)


# ── score_citation ────────────────────────────────────────────────────────────

def test_citation_drug_name_in_rationale():
    exp = {"key_citations": ["sebetralstat", "Ekterly", "KalVista"]}
    assert score_citation(
        "Sebetralstat is the first oral kallikrein inhibitor for HAE",
        [], [], exp)


def test_citation_in_precedent_drugs():
    exp = {"key_citations": ["inclisiran"]}
    assert score_citation("", ["inclisiran (Leqvio)"], [], exp)


def test_citation_no_match():
    exp = {"key_citations": ["sebetralstat"]}
    assert not score_citation("PCSK9 antibody", [], [], exp)


# ── Wilson CI ─────────────────────────────────────────────────────────────────

def test_wilson_ci_perfect():
    lo, hi = wilson_ci(16, 16)
    assert hi == 1.0
    assert lo > 0.7   # 16/16 with z=1.96 has lower bound ~0.79


def test_wilson_ci_zero():
    lo, hi = wilson_ci(0, 16)
    assert lo == 0.0
    assert hi < 0.3


def test_wilson_ci_half_small_n():
    lo, hi = wilson_ci(3, 6)
    assert lo < 0.5 < hi
    assert hi - lo > 0.4   # small N -> wide CI


def test_wilson_ci_n_zero():
    lo, hi = wilson_ci(0, 0)
    assert lo == hi == 0.0


# ── helpers ───────────────────────────────────────────────────────────────────

def test_symbols_filters_blocklist():
    syms = _symbols("AAV9 delivers SMN1 transgene; uses ATP")
    assert "SMN1" in syms
    assert "AAV9" not in syms
    assert "ATP" not in syms


def test_is_generic_alias():
    assert _is_generic_alias("gene therapy")
    assert _is_generic_alias("inhibitor")
    assert _is_generic_alias("antibody")
    assert not _is_generic_alias("KLKB1")
    assert not _is_generic_alias("CRH receptor")


# ── disease-gene-default rate ─────────────────────────────────────────────────
#
# These tests mirror the inline computation in sandbox/run_blinded.py.
# Keep them in sync; if the run_blinded code changes the canonicalization
# of predicted_target, expected_target, or gene, the test should be
# updated to match (and the README number should also be re-derived).

import re as _re


def _canon(t: str) -> str:
    if not t:
        return ""
    m = _re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", t)
    return (m.group(0) if m else t.strip()).upper()


def _dg_default_rate(results: list[dict]) -> tuple[int, int, float]:
    """Mirror the disease-gene-default-rate computation. Returns
    (n_default_when_diverge, n_diverge_cases, rate)."""
    n_diverge = 0
    n_default = 0
    for r in results:
        pred = _canon(r.get("predicted_target") or "")
        gene = _canon(r.get("gene") or "")
        exp  = _canon(r.get("expected_target") or "")
        if gene and exp and gene != exp:
            n_diverge += 1
            if pred == gene:
                n_default += 1
    rate = n_default / n_diverge if n_diverge else 0.0
    return n_default, n_diverge, rate


def test_dg_default_rate_zero():
    # No case diverges (target == disease gene), so rate is undefined → 0.
    results = [
        {"gene": "HBB", "expected_target": "HBB", "predicted_target": "HBB"},
    ]
    n, d, r = _dg_default_rate(results)
    assert (n, d, r) == (0, 0, 0.0)


def test_dg_default_rate_all_default():
    # Every diverging case predicted the disease gene → 100% default.
    results = [
        {"gene": "CYP21A2", "expected_target": "CRHR1", "predicted_target": "CYP21A2"},
        {"gene": "BMPR2",   "expected_target": "ACVR2A", "predicted_target": "BMPR2"},
        {"gene": "PIGA",    "expected_target": "CFB",    "predicted_target": "PIGA (mRNA)"},
    ]
    n, d, r = _dg_default_rate(results)
    assert n == 3 and d == 3 and r == 1.0


def test_dg_default_rate_mixed():
    # 1 default, 1 recovered, 1 wrong-but-not-default; only the first counts as default.
    results = [
        {"gene": "CYP21A2", "expected_target": "CRHR1", "predicted_target": "CYP21A2"},
        {"gene": "BMPR2",   "expected_target": "ACVR2A", "predicted_target": "ACVR2A"},
        {"gene": "PIGA",    "expected_target": "CFB",    "predicted_target": "CD55"},
    ]
    n, d, r = _dg_default_rate(results)
    assert n == 1 and d == 3 and r == 1/3


def test_dg_default_rate_ignores_target_equals_gene_cases():
    # Cases where the FDA target IS the disease gene aren't part of the
    # denominator. They should be excluded.
    results = [
        {"gene": "SMN1", "expected_target": "SMN1", "predicted_target": "SMN1"},
        {"gene": "CYP21A2", "expected_target": "CRHR1", "predicted_target": "CYP21A2"},
    ]
    n, d, r = _dg_default_rate(results)
    assert d == 1 and n == 1 and r == 1.0
