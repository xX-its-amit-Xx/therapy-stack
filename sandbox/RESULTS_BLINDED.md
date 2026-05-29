# Blinded benchmark: model + pipeline ablation

Test set: 10 YAML cases in `therapy-agent/benchmarks/`. 
Input per case: `gene + mutation + disease_phenotype` only.  
No FDA drug names or targets passed to the agent. All test-set
leakage stripped in v0.3.

## Ablation summary

| # | Version | Model + pipeline | Target | Hard | Easy | Modality | Citation | Wall (min) |
|---|---|---|---|---|---|---|---|---|
| v0.4 | 3B (Tier 0 only) | 3/10 | 3/5 | 0/5 | 3/10 | 4/10 | 17 |
| v0.5 | 3B + Tier 1 | 5/10 | 1/5 | 4/5 | 4/10 | 2/10 | 20 |
| v0.6 | Llama 3.1 8B + Tier 1 | 6/10 | 2/5 | 4/5 | 7/10 | 3/10 | 34 |
| v0.7 | R1-Distill 8B + Tier 1 | 7/10 | 3/5 | 4/5 | 4/10 | 2/10 | 82 |

**Baselines (no LLM):**  
- always-predict-disease-gene: 5/10
- first-Reactome-interactor: 5/10

## What Tier 1 actually did

Three changes inside the LangGraph and prompts, no model swap:

1. **Decomposed `strategy_synthesis` into two focused LLM calls** instead of one omnibus call. Stage 1 picks the categorical pattern (1-8) and target_kind. Stage 2 picks the specific gene from the candidates, conditioned on Stage 1's pattern. Smaller scope per call = less long-instruction fatigue.
2. **Self-consistency vote on the Stage 2 target pick** -- 3 samples at temperature 0.5, majority vote on the canonical HGNC symbol. Confidence = vote margin (3/3 -> 0.9, 2/3 -> 0.7, 1/3 -> 0.5).
3. **`self_critique` now always fires** (not just on low confidence). Specifically checks whether `target_protein` matches the rationale; if not, writes the corrected gene into `target_protein`. Closes the v0.4 failure mode where rationale named TMED9 but `target_protein` said UMOD.

Plus a YAML cleanup: removed `LDLR` from the `fh_pcsk9` alias bag (LDLR is a different therapeutic target, not a PCSK9 synonym) and removed `SMN1` from `sma_smn1` (disease gene shouldn't be in target aliases for a paralog-augmentation strategy).

## What the ablation shows

- **Tier 1 + 3B (v0.5)** flipped the case mix: easy cases up (0/5 -> 4/5), hard cases down (3/5 -> 1/5). The decomposition makes the 3B more conservative -- when in doubt it falls back to the disease gene. Net 5/10 but below the 6/10 baseline.
- **Tier 1 + Llama 3.1 8B (v0.6)** doesn't decisively beat baseline by total (6/10 = baseline) but recovers 2 hard cases by reasoning (BRD4780/TMED9 from UniProt SUBUNIT chunks; SMA/SMN1-mRNA from paralog biology). Modality matching jumps to 7/10 -- 8B is much better at the pattern -> modality mapping.
- **Tier 1 + R1-Distill-Llama-8B (v0.7)** is the only configuration that beats baseline cleanly: **7/10 total, 3/5 hard**, including SERPING1 -> KLKB1 (first time recovered without leakage). The reasoning model spends ~2.5x more wall time per case but actually uses the extra tokens to chain 'LOF inhibitor -> downstream protease -> phenotype matches kinin axis -> KLKB1.'

## Per-case (v0.7 R1-Distill detail)

| Case | Type | Gene | Expected | Predicted | Target? | Modality? |
|---|---|---|---|---|---|---|
| `brd4780_umod` | hard | UMOD | TMED9 | `TMED9` | Y | Y |
| `ekterly_serping1` | hard | SERPING1 | KLKB1 | `KLKB1` | Y | Y |
| `als_sod1` | easy | SOD1 | SOD1 | `CCS` | N | N |
| `dmd_exon51` | easy | DMD | DMD | `DMD` | Y | Y |
| `fabry_gla` | easy | GLA | GLA | `GLA` | Y | N |
| `fh_pcsk9` | easy | PCSK9 | PCSK9 | `PCSK9 (mRNA)` | Y | Y |
| `obesity_pomc` | hard | POMC | MC4R | `POMC (mRNA)` | N | N |
| `porphyria_alas1` | hard | HMBS | ALAS1 | `FECH` | N | N |
| `scd_hbb` | easy | HBB | HBB | `HBB (mRNA)` | Y | N |
| `sma_smn1` | hard | SMN1 | SMN2 | `SMN2` | Y | N |

## What's still wrong

Three persistent failures across all v0.5-v0.7 configurations:

- **`als_sod1` (SOD1 expected, model picks CCS).** CCS is the copper chaperone for SOD1; the model reasons 'reduce CCS to destabilize toxic SOD1 aggregates' which is a real (but not FDA-approved) strategy.
- **`obesity_pomc` (MC4R expected, model picks POMC).** Stage 1 pattern selector picks pattern 5 (toxic gain mRNA knockdown) instead of pattern 6 (receptor agonist bypass). Phenotype doesn't disambiguate strongly enough.
- **`porphyria_alas1` (ALAS1 expected, model picks FECH or HMBS).** Even with explicit g2p-rag chunks naming ALAS1 as the first committed step, the model goes for the most-recently-mentioned enzyme. This is the case where a graph algorithm over Reactome would beat the LLM deterministically.

## Next levers (untried)

- **Frontier model (Claude / GPT-4) with the same pipeline.** One API call away; the pipeline is unchanged.
- **Tool-use agentic loop.** Let the LLM issue follow-up retrieval calls ('list upstream enzymes of HMBS in heme biosynthesis'). The fixed-flow LangGraph doesn't allow this today.
- **Hybrid graph + LLM.** Compute 'upstream rate-limiting enzyme' deterministically from Reactome edges for cases that match the pattern. Would deterministically fix porphyria.
- **Held-out test set of post-2024 FDA approvals.** N=10 means 95% CI of +/-26 pp; differences within the table are noisy.