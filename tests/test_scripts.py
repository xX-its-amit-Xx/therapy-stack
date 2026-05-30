"""Tests for the analysis scripts in scripts/.

These tests don't run the full bench -- they call the script functions
directly with synthetic result data to lock in the classification
semantics.

Run with: pytest tests/test_scripts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "scripts"))


# ── miss_taxonomy ─────────────────────────────────────────────────────────────

def test_miss_taxonomy_disease_gene_default():
    from miss_taxonomy import classify
    case = {
        "case_id": "test",
        "gene": "CYP21A2",
        "expected_target": "CRHR1",
        "predicted_target": "CYP21A2",
    }
    assert classify(case) == "disease_gene_default"


def test_miss_taxonomy_paralog_confusion():
    from miss_taxonomy import classify
    # PIGA -> C5 is the FDA case; if the agent predicted CFB instead,
    # it's paralog_confusion under GPI_anchor_complement family.
    case = {
        "case_id": "test",
        "gene": "PIGA",
        "expected_target": "C5",
        "predicted_target": "CFB",
    }
    assert classify(case) == "paralog_confusion"


def test_miss_taxonomy_confabulation():
    from miss_taxonomy import classify
    # Predicted is in neither family.
    case = {
        "case_id": "test",
        "gene": "PIGA",
        "expected_target": "C5",
        "predicted_target": "TP53",
    }
    assert classify(case) == "confabulation_off_pathway"


def test_miss_taxonomy_no_prediction():
    from miss_taxonomy import classify
    case = {
        "case_id": "test",
        "gene": "PIGA",
        "expected_target": "C5",
        "predicted_target": "",
    }
    assert classify(case) == "no_prediction"


# ── pattern_correctness ───────────────────────────────────────────────────────

def test_expected_pattern_disease_gene():
    from pattern_correctness import _expected_pattern
    assert _expected_pattern("HBB", "HBB").startswith("5")  # disease-gene-centric


def test_expected_pattern_feedback_axis():
    from pattern_correctness import _expected_pattern
    assert _expected_pattern("CYP21A2", "CRHR1") == "9"


def test_expected_pattern_paralog():
    from pattern_correctness import _expected_pattern
    # SMN1 -> SMN2 (paralog reactivation; same root, different digit).
    assert _expected_pattern("SMN1", "SMN2") == "2/8"


def test_expected_pattern_downstream():
    from pattern_correctness import _expected_pattern
    # SERPING1 (LoF inhibitor) -> KLKB1 (unbraked downstream).
    assert _expected_pattern("SERPING1", "KLKB1") == "1/3/6"


# ── benchmark_lint ────────────────────────────────────────────────────────────

def test_lint_passes_on_current_yamls():
    """The lint should currently pass on all 35 YAML cases."""
    from benchmark_lint import _lint
    assert _lint(strict=False) == 0


# ── replicate_budget ──────────────────────────────────────────────────────────

def test_replicate_budget_small_improvement():
    from replicate_budget import replicates_needed
    # Detecting +2 cases of 12 at 8% flip rate needs ~5 replicates.
    assert replicates_needed(flip_rate=0.08, delta=2,
                              n_cases=12, alpha=0.05, power=0.8) >= 3


def test_replicate_budget_big_improvement():
    from replicate_budget import replicates_needed
    # Detecting +5 cases of 12 should need many fewer replicates.
    big = replicates_needed(flip_rate=0.08, delta=5, n_cases=12)
    small = replicates_needed(flip_rate=0.08, delta=2, n_cases=12)
    assert big <= small


def test_replicate_budget_zero_delta():
    from replicate_budget import replicates_needed
    assert replicates_needed(flip_rate=0.08, delta=0, n_cases=12) == 0
