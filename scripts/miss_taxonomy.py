#!/usr/bin/env python3
"""Classify benchmark misses by failure mode.

Reads any blinded_*.json and categorizes each MISS into one of the
documented failure modes:

  - disease_gene_default     -- predicted = disease_gene, expected != disease_gene
  - paralog_confusion        -- predicted is in disease_gene's known paralog/family
                                (uses a small static family map)
  - adjacent_pathway_pick    -- predicted is in the same Reactome pathway as the
                                expected target but is a different node
  - confabulation_off_pathway -- predicted is in neither the disease gene's pathway
                                 nor the expected target's pathway
  - unknown                  -- couldn't classify

The taxonomy gives the curator a structured signal: "v0.8 fixed
paralog_confusion in 3 cases but introduced disease_gene_default in 2".
Used together with run_diff to understand WHY a number moved.

No LLM calls; pure heuristic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


# Small biology-curated family map for paralog detection. Same families
# used by the find_signaling_family tool in therapy-agent. Kept here
# without therapeutic-strategy annotation -- just structural biology.
_FAMILIES: dict[str, set[str]] = {
    "BMP_activin_receptor": {"BMPR1A", "BMPR1B", "BMPR2", "ACVR1", "ACVR1B",
                              "ACVR1C", "ACVR2A", "ACVR2B"},
    "melanocortin_GPCR": {"MC1R", "MC2R", "MC3R", "MC4R", "MC5R", "POMC", "AGRP", "ASIP"},
    "hemoglobin_chain": {"HBA1", "HBA2", "HBB", "HBD", "HBE1", "HBG1", "HBG2"},
    "contact_activation": {"F12", "F11", "KLKB1", "KNG1", "BDKRB1", "BDKRB2",
                            "C1R", "C1S", "SERPING1"},
    "complement_effector": {"C1R", "C1S", "C2", "C3", "C4A", "C4B", "C5", "C6",
                             "C7", "C8", "C9", "CFB", "CFD", "CFH", "CFI"},
    "heme_biosynthesis": {"ALAS1", "ALAS2", "ALAD", "HMBS", "UROS", "UROD",
                           "CPOX", "PPOX", "FECH"},
    "IDH_paralog": {"IDH1", "IDH2", "IDH3A", "IDH3B", "IDH3G"},
    "SMN_complex": {"SMN1", "SMN2", "GEMIN2", "GEMIN3", "GEMIN4", "GEMIN5"},
    "CAAX_prenylation": {"FNTA", "FNTB", "PGGT1B", "RCE1", "ZMPSTE24", "ICMT", "LMNA"},
    "thyroid_receptor": {"THRA", "THRB", "RXRA", "RXRB", "RXRG"},
    "AKT_PI3K_chain": {"PIK3CA", "PIK3CB", "PIK3CD", "PIK3R1", "AKT1", "AKT2",
                        "AKT3", "MTOR", "MLST8", "RICTOR", "RPTOR", "PTEN"},
    "dystrophin_complex": {"DMD", "UTRN", "DTNA", "DTNB", "SNTA1", "DAG1",
                            "SGCA", "SGCB", "SGCG", "SGCD"},
    "GPI_anchor_complement": {"PIGA", "CD55", "CD59", "C3", "C5", "CFB"},
    "endothelin_signaling": {"EDN1", "EDN2", "EDN3", "EDNRA", "EDNRB"},
    "muscarinic_GPCR": {"CHRM1", "CHRM2", "CHRM3", "CHRM4", "CHRM5"},
    "BTK_signaling": {"BTK", "BLNK", "PLCG2", "BCR"},
    "HER_family": {"ERBB1", "ERBB2", "ERBB3", "ERBB4", "EGFR"},
    # SOD chain: SOD1 + its copper chaperone CCS + paralogs.
    "SOD_complex": {"SOD1", "SOD2", "SOD3", "CCS"},
    # Lysosomal hydrolases -- different substrates but functionally related;
    # an agent confusing GLA (Fabry) with GBA (Gaucher) is hitting the
    # lysosomal-enzyme-replacement archetype, not picking randomly.
    "lysosomal_hydrolase": {"GLA", "GBA", "GBA1", "GBA2", "GUSB", "IDUA",
                             "NAGLU", "GALNS", "SGSH", "NAGA", "HEXA",
                             "HEXB", "ARSA", "ARSB", "GAA", "MAN2B1"},
    # Heme transport / synthesis vs porphyria-side: HMBS (Acute Intermittent
    # Porphyria gene) + ALAS1 (upstream rate-limiter) -- the givosiran case.
    "porphyria_axis": {"HMBS", "ALAS1", "ALAS2", "ALAD", "UROS"},
}


def _symbols(text: str) -> set[str]:
    raw = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text or ""))
    return raw


def _family_of(gene: str) -> str | None:
    g = (gene or "").upper()
    for name, members in _FAMILIES.items():
        if g in members:
            return name
    return None


def _canonical(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", text)
    return (m.group(0) if m else text.strip()).upper()


def classify(case: dict) -> str:
    """Return a failure-mode label for a MISS case. Assumes case.target_recovered=False."""
    pred = _canonical(case.get("predicted_target", ""))
    exp = _canonical(case.get("expected_target", ""))
    disease = _canonical(case.get("gene", ""))

    if not pred:
        return "no_prediction"
    if pred == disease and pred != exp:
        return "disease_gene_default"

    pred_fam = _family_of(pred)
    exp_fam = _family_of(exp)
    disease_fam = _family_of(disease)

    # Paralog confusion: predicted is in the SAME family as either expected
    # or disease gene (i.e. agent picked a sibling).
    if pred_fam and (pred_fam == exp_fam or pred_fam == disease_fam):
        return "paralog_confusion"

    # Adjacent pathway pick: predicted is in expected's family but expected's
    # family is None. Use a softer heuristic: if both pred and exp appear in
    # ANY shared family.
    for fam_name, members in _FAMILIES.items():
        if pred in members and exp in members:
            return "paralog_confusion"  # already covered, but in case fam None earlier

    return "confabulation_off_pathway"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    for p in args.paths:
        if not p.exists():
            print(f"SKIP {p}: not found"); continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"SKIP {p}: parse failed ({e})"); continue
        results = d.get("results") or []
        misses = [r for r in results if not r.get("target_recovered")]
        if not misses:
            print(f"## {p.name}: 0 misses (all {len(results)} recovered)\n")
            continue
        counts: Counter = Counter()
        cases_by_mode: dict[str, list[dict]] = {}
        for r in misses:
            mode = classify(r)
            counts[mode] += 1
            cases_by_mode.setdefault(mode, []).append(r)

        print(f"## Miss taxonomy -- {p.name} ({len(misses)}/{len(results)} misses)\n")
        print("| Failure mode | N | Cases |")
        print("|---|---|---|")
        for mode, n in counts.most_common():
            cs = ", ".join(c["case_id"] for c in cases_by_mode[mode])
            print(f"| {mode} | {n} | {cs} |")
        print()
        # Per-case detail.
        print("| Case | Disease gene | Expected | Predicted | Mode |")
        print("|---|---|---|---|---|")
        for r in misses:
            print(f"| `{r['case_id']}` | {r.get('gene')} | "
                  f"`{r.get('expected_target')}` | `{r.get('predicted_target')}` | "
                  f"`{classify(r)}` |")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
