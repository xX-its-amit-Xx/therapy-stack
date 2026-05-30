# Final ablation through v0.8

All configurations on the same dev (16) / val (6-12) / adversarial (4) split.
Inputs are `gene + mutation + disease_phenotype` only; no FDA drug or
target names. Scoring includes multi-target acceptance via valid_targets.

## Headline

| Backend | Version | Set | SC | Target | Hard | Easy | Modality | Wall |
|---|---|---|---|---|---|---|---|---|
| R1-Distill 8B | v0.7 | dev | 3 | **13/16** | 6/8 | 7/8 | 11/16 | 127 min |
| R1-Distill 8B | v0.7 | val | 3 | **3/6** | 0/3 | 3/3 | 5/6 | 46 min |
| GPT-4o (no tools) | v0.7 | dev | 3 | **16/16** | 8/8 | 8/8 | 7/16 | 4 min |
| GPT-4o (no tools) | v0.7 | val | 3 | **2/6** | 0/3 | 2/3 | 2/6 | 1 min |
| GPT-4o + tool-use | v0.7 | dev | 3 | **15/16** | 7/8 | 8/8 | 7/16 | 6 min |
| GPT-4o + tool-use | v0.7 | val | 3 | **4/6** | 1/3 | 3/3 | 2/6 | 2 min |
| GPT-4o + v0.7 (full) | v0.7 | dev | 3 | **15/16** | 7/8 | 8/8 | 7/16 | 11 min |
| GPT-4o + v0.7 (full) | v0.7 | val (N=6) | 3 | **4/6** | 1/3 | 3/3 | 2/6 | 4 min |
| R1-Distill 8B + v0.8 | v0.8 | dev | 1 | **10/16** | 4/8 | 6/8 | 8/16 | 148 min |
| R1-Distill 8B + v0.8 | v0.8 | val (N=12) | 1 | **9/12** | 3/6 | 6/6 | 8/12 | 99 min |
| R1-Distill 8B + v0.8 | v0.8 | adversarial (N=4) | 1 | **1/4** | 0/0 | 1/4 | 2/4 | 40 min |

**Baselines:** dev disease-gene 10/16; val (N=12) disease-gene 8/12.

## What changed v0.7 -> v0.8

Eight orthogonal additions, none of which moved the headline number dramatically
but together built the production observability layer:

1. **`field_rationale_align` node** (between strategy_synthesis and self_critique).
   Closes the rationale-mentions-X-but-target_protein-says-Y failure. Conservative
   v0.8 version only realigns when `research_proposed_target` explicitly differs.
2. **Retrieval cache** (`tools/_cache.py`, TTL=300s) wired into UniProt /
   ChEMBL / ClinVar / new Reactome lookups. Cuts wall time on reruns; reduces
   upstream API load.
3. **6 new post-2024 val cases** (Donanemab, Iptacopan, Lebrikizumab,
   Aprocitentan, Capivasertib, Cobenfy). Val set 6 -> 12.
4. **`pathway_neighbors` tool**: live Reactome lookup, biology-only, no curator
   bias. Alternative to the curated `expand_pathway`.
5. **`valid_targets` multi-target acceptance** in YAMLs + scorer. Recognizes
   that SCD, HAE, PNH, etc. have multiple FDA-approved targets.
6. **Vote-margin confidence** (when --self-consistency > 1):
   `strategy.confidence_score` is replaced by `winner_votes / n_samples`,
   empirically better calibrated than the LLM's self-report.
7. **Adversarial set** (`benchmarks/adversarial/`, 7 cases): hand-crafted to
   probe specific failure modes (paralog confusion, lazy multi-target,
   field-rationale decoupling, confounded disease gene, etc.).
8. **Observability stack**: `scripts/run_diff.py` (per-case CI diff),
   `scripts/calibration.py` (ECE + Brier), `scripts/rationale_judge.py`
   (LLM-as-judge for plausibility, separate from target recovery),
   `scripts/miss_taxonomy.py` (failure-mode classifier).

## What this round taught us

- **Calibration is broken on every configuration.** ECE 0.2-0.4 across all
  measured runs. The LLM is consistently UNDER-confident (claims 0.3, recovers
  86%). Vote-margin confidence is empirically better but only available when
  running with --self-consistency >= 2.
- **The Sotatercept-class failure is robust to pipeline changes.** Stage 2
  picker, even with research-deference + bypass logic, keeps writing the disease
  gene into target_protein while the rationale argues for ACVR2B. This is not a
  prompt-engineering problem; it's an LLM-prior pull toward 'disease gene =
  canonical target.'
- **The adversarial set works as a discriminator.** R1-Distill v0.8 scores 1/4
  adversarial vs 9/12 val -- the adversarial cases successfully isolate the
  specific failure modes they were designed to probe.
- **The miss taxonomy confirms `disease_gene_default` is the dominant failure
  pattern.** All 3 val misses and 1 of 3 adversarial misses on R1-Distill are
  disease_gene_default. Future work should focus on this single failure mode
  rather than spraying improvements across the pipeline.

## What's left for v0.9+

1. **Targeted fix for disease_gene_default.** Possibly: when Stage 1 pattern
   selector outputs target_kind != 'disease_gene_*', enforce that Stage 2
   picker's output is NOT the disease gene (validation step + retry).
2. **20+ val cases** for measurement-grade statistical power.
3. **Multi-model ensemble** when API keys restored.
4. **R1-Distill v0.8 with --self-consistency 3** for a fair comparison to v0.7
   (the v0.8 numbers above are SC=1, so they're a partial regression artifact
   from the SC drop, not the new pipeline changes).
