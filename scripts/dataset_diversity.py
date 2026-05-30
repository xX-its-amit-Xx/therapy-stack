#!/usr/bin/env python3
"""Dataset diversity report for the blinded benchmark splits.

Reads the YAML benchmark cases (dev / val / adversarial) and reports
the distribution across:
  - target_kind (disease_gene / downstream_effector / paralog / ...)
  - modulation_type (inhibitor / agonist / siRNA_ASO / antibody / ...)
  - therapeutic area (oncology / cardiovascular / neuro / metabolic /
    rare hematology / ...)

A balanced split should look like the disease + target landscape, not
just "small molecules against kinases". This script makes that visible.

Usage:
    python scripts/dataset_diversity.py
    python scripts/dataset_diversity.py --markdown > sandbox/DIVERSITY.md
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import yaml  # type: ignore[import]


_AGENT_REPO = Path(__file__).resolve().parents[1].parent / "therapy-agent"
_BM_DIR = _AGENT_REPO / "benchmarks"

# Therapeutic-area inference rules from disease keywords. Cheap heuristic;
# a curator-set field would be cleaner.
_AREA_RULES = [
    ("oncology",        ("cancer", "tumor", "lymphoma", "leukemia",
                         "glioma", "melanoma", "carcinoma", "myeloma")),
    ("cardiovascular",  ("ldl", "hypertension", "hypercholester",
                         "pulmonary hypertens", "thrombo", "heart")),
    ("metabolic",       ("diabet", "obesity", "porphyria", "fabry",
                         "alpha-1", "amyloid", "homocyst")),
    ("neuro",           ("alzheimer", "schizo", "depression", "park",
                         "als ", "spinal muscular", "duchenne", "rett",
                         "migraine", "epilep", "huntington")),
    ("rare hematology", ("sickle cell", "hemophilia", "thalassemia",
                         "pnh", "paroxysmal", "hae", "angioedema")),
    ("inflammation",    ("psoriasis", "atopic", "rheumat", "lupus",
                         "ibd", "crohn", "colitis", "uveitis")),
    ("renal",           ("medullary cystic", "polycyst", "iga ",
                         "nephropath", "lupus nephritis")),
    ("ophth",           ("amd", "macular", "stargardt", "leber")),
    ("endocrine",       ("cah ", "adrenal hyperplasia", "acromeg",
                         "cushing", "thyroid")),
]


def _area_for(disease: str) -> str:
    d = (disease or "").lower()
    for area, kws in _AREA_RULES:
        if any(k in d for k in kws):
            return area
    return "other"


def _split_dirs() -> dict[str, list[Path]]:
    return {
        "dev": [_BM_DIR, _BM_DIR / "cases"],
        "val": [_BM_DIR / "heldout_2024_2025"],
        "adversarial": [_BM_DIR / "adversarial"],
    }


def _iter_cases(split: str):
    for d in _split_dirs()[split]:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.yaml")):
            try:
                doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(doc, dict):
                yield f.name, doc


def _target_kind(gene: str, target_protein: str) -> str:
    """Infer target_kind from the relationship between disease gene and target.

    The YAMLs don't tag this directly, so we infer:
      - 'disease_gene' if target == gene (rare in this benchmark; HBB, SMN1...)
      - 'paralog' if target is a known paralog/family member (BCL11A for SCD)
      - 'downstream_effector' otherwise (the typical pattern)
    """
    g = (gene or "").strip().upper()
    # Normalize target_protein to leading HGNC symbol if possible.
    t = (target_protein or "").strip().split()[0].rstrip(",").upper() if target_protein else ""
    if not g or not t:
        return "?"
    if g == t:
        return "disease_gene"
    # Heuristic for paralogs/family: same prefix + numeric suffix.
    import re
    g_root = re.sub(r"\d+$", "", g)
    t_root = re.sub(r"\d+$", "", t)
    if g_root and g_root == t_root and g != t:
        return "paralog"
    return "downstream_effector"


def _summarize(split: str) -> dict:
    target_kind = collections.Counter()
    modulation  = collections.Counter()
    area        = collections.Counter()
    n_multi     = 0
    n           = 0
    for _, doc in _iter_cases(split):
        n += 1
        inp = doc.get("input", {}) or {}
        exp = doc.get("expected_outputs", {}) or {}
        gene = inp.get("gene", "")
        tgt = exp.get("target_protein") or ""
        tk  = _target_kind(gene, tgt)
        mt  = exp.get("modulation_type") or "?"
        ar  = _area_for(inp.get("disease_phenotype", ""))
        target_kind[tk] += 1
        modulation[mt]  += 1
        area[ar]        += 1
        if exp.get("valid_targets"):
            n_multi += 1
    return {
        "n": n,
        "target_kind": dict(target_kind),
        "modulation":  dict(modulation),
        "area":        dict(area),
        "n_multi_target": n_multi,
    }


def _print_counter(label: str, c: dict, total: int) -> None:
    print(f"### {label}")
    print()
    print("| Value | N | % |")
    print("|---|---|---|")
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        pct = (v / total * 100) if total else 0
        print(f"| `{k}` | {v} | {pct:.0f}% |")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true",
                    help="emit markdown (default: stdout summary)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    splits = ("dev", "val", "adversarial")
    summaries = {s: _summarize(s) for s in splits}

    print("# Dataset diversity")
    print()
    print("How balanced is the benchmark across target-kinds, modalities,")
    print("and therapeutic areas? A split that's 80% oncology is a")
    print("different benchmark than one that's spread across 6 areas.")
    print()
    print("| Split | N | Multi-target cases |")
    print("|---|---|---|")
    for s in splits:
        sm = summaries[s]
        print(f"| {s} | {sm['n']} | {sm['n_multi_target']} |")
    print()

    for s in splits:
        sm = summaries[s]
        print(f"## Split: {s} (N={sm['n']})")
        print()
        _print_counter("Target kind", sm["target_kind"], sm["n"])
        _print_counter("Modulation type", sm["modulation"], sm["n"])
        _print_counter("Therapeutic area", sm["area"], sm["n"])

    # Cross-split summary: do dev and val cover the same modalities?
    print("## Cross-split: modality coverage gap")
    print()
    dev_mods = set(summaries["dev"]["modulation"])
    val_mods = set(summaries["val"]["modulation"])
    adv_mods = set(summaries["adversarial"]["modulation"])
    print(f"- Modalities in dev only: `{sorted(dev_mods - val_mods - adv_mods)}`")
    print(f"- Modalities in val only: `{sorted(val_mods - dev_mods - adv_mods)}`")
    print(f"- Modalities in adv only: `{sorted(adv_mods - dev_mods - val_mods)}`")
    print(f"- Modalities in all 3:    `{sorted(dev_mods & val_mods & adv_mods)}`")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
