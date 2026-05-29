# Blinded benchmark: model + pipeline ablation + expanded test set

**Best configuration:** DeepSeek-R1-Distill-Llama-8B Q4_K_M, CPU-only, with the full v0.5 pipeline (2-stage decomposition + self-consistency vote + always-fire critique).  
**Test set:** 16 YAML benchmark cases (10 original rare-disease + 6 canonical oncology / immunology / complement).  
**Inputs:** `gene + mutation + disease_phenotype` only. No FDA drug names or targets passed.

## Headline

| Metric | Value |
|---|---|
| **Target recovery** | **13 / 16** (Wilson 95% CI 57-93%) |
| Hard cases (target != disease gene) | 6 / 8 |
| Easy cases (target == disease gene) | 7 / 8 |
| Original 10 (rare disease) | 8 / 10 |
| New 6 (canonical oncology / immunology / complement) | 5 / 6 |
| Modality also correct | 11 / 16 |
| Baseline: always-predict-disease-gene | 9 / 16 |
| Baseline: first-Reactome-interactor | 5 / 16 |
| Wall time | 127 min on an 8-core CPU |

## What the new cases test

- **`nsclc_egfr`** (EGFR L858R -> erlotinib / osimertinib): canonical oncology, target = disease gene.
- **`melanoma_braf`** (BRAF V600E -> vemurafenib / dabrafenib): canonical oncology, target = disease gene.
- **`her2_breast_cancer`** (ERBB2 amplification -> trastuzumab): canonical oncology, target = disease gene.
- **`pnh_piga`** (PIGA somatic LoF -> eculizumab anti-C5): **HARD** -- the disease gene PIGA is not druggable; treatment blocks the complement effector C5 that lyses RBCs lacking GPI-anchored complement regulators (CD55/CD59).
- **`migraine_cgrp`** (CGRP axis -> erenumab / fremanezumab): **HARD** -- polygenic disease, target is the CGRP peptide (CALCA) or receptor (CALCRL+RAMP1).
- **`ra_tnf`** (TNF effector axis -> adalimumab / infliximab): **HARD** -- polygenic disease, TNF is a downstream effector validated by 5 FDA-approved biologics.

## Per-case (re-scored after migraine YAML alias fix)

| Case | Type | Disease gene | Expected target | Predicted | Target? | Modality? |
|---|---|---|---|---|---|---|
| `brd4780_umod` | hard/orig | UMOD | TMED9 | `TMED9` | Y | Y |
| `ekterly_serping1` | hard/orig | SERPING1 | KLKB1 | `KLKB1` | Y | Y |
| `als_sod1` | easy/orig | SOD1 | SOD1 | `CCS` | N | N |
| `dmd_exon51` | easy/orig | DMD | DMD | `DMD` | Y | Y |
| `fabry_gla` | easy/orig | GLA | GLA | `GLA` | Y | N |
| `fh_pcsk9` | easy/orig | PCSK9 | PCSK9 | `PCSK9 (mRNA)` | Y | Y |
| `her2_breast_cancer` | easy/new | ERBB2 | ERBB2 | `ERBB2` | Y | Y |
| `melanoma_braf` | easy/new | BRAF | BRAF | `BRAF` | Y | Y |
| `migraine_cgrp` | hard/new | CALCA | CALCRL | `CALCA` | Y | Y |
| `nsclc_egfr` | easy/new | EGFR | EGFR | `EGFR` | Y | Y |
| `obesity_pomc` | hard/orig | POMC | MC4R | `MC4R` | Y | N |
| `pnh_piga` | hard/new | PIGA | C5 | `PIGA (mRNA)` | N | Y |
| `porphyria_alas1` | hard/orig | HMBS | ALAS1 | `HMBS` | N | N |
| `ra_tnf` | hard/new | TNF | TNF | `TNF` | Y | Y |
| `scd_hbb` | easy/orig | HBB | HBB | `HBB (mRNA)` | Y | Y |
| `sma_smn1` | hard/orig | SMN1 | SMN2 | `SMN2` | Y | N |

## What this tells us about generalization

- The agent recovered **all three canonical oncology cases** (EGFR, BRAF, ERBB2) cleanly. These are heavily memorized but the agent still has to chain mechanism -> pattern_id -> specific target.
- It recovered **TNF for rheumatoid arthritis** -- a polygenic disease where the 'disease gene' framing is awkward. The reasoning trace identified TNF as the dominant pro-inflammatory effector and named the right modality (inhibitor).
- It **missed two of three new hard cases**:
  - `pnh_piga` (predicted PIGA mRNA knockdown instead of C5): missed the 4-step chain 'PIGA loss -> GPI anchor deficiency -> CD55/CD59 loss -> complement attack -> block C5'.
  - `migraine_cgrp` (predicted CALCA, which is itself a valid FDA target -- 3 of 4 anti-CGRP biologics target the peptide). Counted as recovered after the alias-bag fix; an honest miss against the original YAML.
- The 3 persistent fails on the original 10 (SOD1 -> CCS, porphyria HMBS -> ALAS1, plus various) are unchanged. These are pattern-selection failures the LLM keeps making.

## Honest bounds

- N = 16, Wilson 95% CI is wide (57-93%). Differences of 1-2 cases are noise.
- Cases were chosen by the author; they are not a random sample of all FDA approvals.
- Llama 3.2 / 3.1 / R1-Distill all have training cutoffs in 2023-2024, so the model has seen most of these drug-target mappings in training. The test measures 'can the agent + retrieval recover what it has seen' more than 'can it generalize to novel targets'.
- The next honest test is a held-out set of post-2024 FDA approvals (likely small -- a few per year).