# Comprehensive Benchmarking Study — therapy-stack

## Motivation

Current therapy-stack recovery numbers (75% val / 62% dev / 25% adv) come from a single backend: `llama.cpp` running `DeepSeek-R1-Distill-Llama-8B` Q4_K_M on local CPU. Three confounds are unresolved:

1. **Quantization loss** — Q4_K_M vs FP16 of the same weights is untested.
2. **Reasoning distillation contribution** — R1-distilled 8B vs vanilla Llama-3.1-8B-Instruct at the same param count has not been ablated.
3. **Scale ceiling** — does 32B Q4 close the gap to 70B FP8, or is the 70B step strictly necessary?

This study answers all three on the existing val / dev / adv splits, plus a per-disease subgroup pass to check whether recovery is concentrated in a few high-prior genes.

## Backend matrix

| # | Backend    | Model                                       | Hardware                                    | Cost class | Wall/case (s) | Expected val recovery                                              |
|---|------------|---------------------------------------------|---------------------------------------------|------------|---------------|--------------------------------------------------------------------|
| 1 | llama.cpp  | DeepSeek-R1-Distill-Llama-8B Q4_K_M         | Local CPU (64 GB, no GPU)                   | free       | 495           | 75% val / 62% dev / 25% adv (baseline, already measured)           |
| 2 | vLLM       | DeepSeek-R1-Distill-Llama-8B FP16           | Kaggle T4 16 GB (single GPU)                | free       | 35            | 75-80% val (same weights; isolates quantization + wall-time)       |
| 3 | vLLM       | Qwen2.5-7B-Instruct FP16                    | Kaggle T4 16 GB                             | free       | 30            | 60-70% val (smaller reasoning-trained competitor at ~same scale)   |
| 4 | vLLM       | Qwen2.5-32B-Instruct Q4_K_M (AWQ)           | Kaggle P100 16 GB OR dual-T4                | free       | 70            | TBM — tests whether 32B Q4 closes gap to 70B FP8                   |
| 5 | vLLM       | Llama-3.1-8B-Instruct FP16                  | Kaggle T4 16 GB                             | free       | 25            | 50-65% val (non-R1-distilled control; isolates R1-distill contrib) |
| 6 | vLLM       | DeepSeek-R1-Distill-Llama-70B FP8           | Explorer cluster — 1x H100 80 GB or 2x A100 | low        | 45            | 80-88% val ("does scale matter at fixed family" test)              |

**Cost class** — free: no marginal $. low: <$50 for the full study at current Explorer rates.

**Wall/case** is single-replicate end-to-end (prompt build → completion → parse → score), not raw token throughput.

## Metrics

Primary:

- **recovery@1** — fraction of cases where the gold therapy is the top-ranked completion. Reported per split (val / dev / adv).
- **recovery@3** — same, top-3.

Secondary:

- **Stage-1 pattern hit rate** (patterns 1-9, see `benchmark_terminology.md`). Pattern-level breakdown is the failure-mode unit.
- **Refusal rate** — fraction of cases where the model emits no rankable candidate.
- **Prompt-leakage rate** — fraction of completions that echo gold-therapy tokens from few-shot exemplars (the v0.11 walkback failure mode; must stay flat or fall vs baseline).
- **Wall-time per case** (median, p95).
- **$/case** for backends in the `low` cost class.

Each metric is reported with a 95% bootstrap CI over cases (10k resamples, BCa).

## Statistical design

- **Unit of analysis** — case (one disease × one variant × one patient profile). N: val 200, dev 150, adv 80.
- **Primary comparison** — paired McNemar test per (backend, split) pair against backend #1 (CPU Q4 baseline). Cases are matched by case-id, so paired tests are valid and strictly more powerful than unpaired.
- **Multiple testing** — Holm-Bonferroni across the 5 non-baseline backends × 3 splits = 15 tests per metric. Family-wise alpha = 0.05.
- **Effect size** — report absolute Δrecovery@1 with 95% bootstrap CI; minimum interesting effect Δ = 5 pp.
- **Power** — at N_val = 200 and baseline 75%, paired McNemar detects Δ = 8 pp at 80% power (alpha = 0.05/15, two-sided). Smaller deltas (≤5 pp) are confirmable only on val; dev and adv are underpowered for sub-5-pp claims and we will flag those as descriptive.
- **Stratification** — per-disease and per-Stage-1-pattern strata reported descriptively; no formal correction at the stratum level.

## Replicate plan

- **Greedy decoding** (temp=0) is the primary configuration. One replicate per case suffices because output is deterministic given the prompt and seed.
- **Sampling sanity check** — for backends 2, 5, and 6, rerun val at temp=0.7, top_p=0.95, **3 replicates per case**, report mean recovery@1 ± SD. If SD > 3 pp on any backend, sampling instability is itself a finding.
- **Seed control** — fixed seed (42) for vLLM sampling. llama.cpp baseline uses seed 0 (already locked in `baselines.json`).
- **Prompt version** — frozen at v0.10 across all backends. v0.11 is excluded per the leakage walkback (commit 1a402fa).
- **Re-run cadence** — full matrix re-run if any of: (a) prompt version changes, (b) any backend ships a new minor release, (c) split contents change.

## Per-disease subgroup analysis

The val split spans the 47-gene cookbook ingest set. Recovery is suspected to concentrate in high-prior genes (BRCA1, BRCA2, CFTR, HBB). The subgroup pass:

1. Bucket cases by gene. Report recovery@1 and N per gene.
2. Flag any gene where baseline recovery is >90% **and** N ≥ 10 — these are likely memorization, not reasoning, and should be excluded from headline numbers.
3. Re-compute headline recovery@1 on the **non-memorized** subset for backends 1, 2, 5, 6. If headline drops >15 pp on the non-memorized subset, the topline recovery claim is reframed as "recovery on memorized genes; recall on novel genes is X."
4. Report per-disease wall-time — long-tail diseases (rare orphanet) may dominate compute.

## Timeline (4-6 weeks)

| Week | Milestone                                                                                                   | Owner / blocker                              |
|------|-------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| 1    | Kaggle vLLM image built; backends 2, 3, 5 smoke-tested on 10 val cases each. Reproduce baseline wall-time.  | Local; no blocker.                           |
| 2    | Full val pass for backends 2, 3, 5 (free tier). Paired McNemar vs baseline. First leakage check.            | Kaggle quota (30 GPU-hr/wk).                 |
| 2-3  | Backend 4 (Qwen 32B AWQ) loadability test on P100. If P100 OOMs, fall back to dual-T4 with TP=2.            | Kaggle P100 availability is bursty.          |
| 3    | Full dev + adv passes for backends 2, 3, 5. Sampling sanity check (temp=0.7, 3 reps) on backend 2.          | Kaggle quota.                                |
| 3-4  | Backend 6 (70B FP8) on Explorer. 1 H100 preferred; 2 A100 fallback. Budget cap: $50.                        | Cluster queue depth.                         |
| 4    | Per-disease subgroup analysis. Identify memorized-gene set. Recompute non-memorized recovery.               | None.                                        |
| 5    | Full re-run of any backend that tripped a re-run trigger. Lock all numbers.                                 | Buffer week.                                 |
| 5-6  | Writeup. Update `SUMMARY.md`, `writeup/`. Tag `v0.12-bench-study`.                                          | None.                                        |

## Open questions

1. **AWQ vs GPTQ for Qwen-32B** — AWQ is the planned quant. If AWQ checkpoint is unavailable on HF, fall back to GPTQ-4bit. Expected delta is small (<2 pp) but worth a one-line note in the writeup.
2. **70B FP8 vs FP16** — FP8 is chosen for the 80 GB H100 fit. If recovery is below 8B FP16, suspect FP8 numerics before declaring "scale doesn't help"; rerun a 20-case slice in FP16 with TP=2 on 2x A100 to confirm.
3. **Adv split N = 80** is underpowered for paired McNemar at Δ < 10 pp. Do we expand adv to N = 150 before locking the matrix, or accept descriptive-only on adv?
4. **Prompt-leakage detector** — current detector is regex on gold-therapy strings. False-negative rate on paraphrased leaks is unmeasured. A 50-case human-graded calibration sample would tighten the leakage metric, but adds 4-6 hours of grading.
5. **Per-gene Bonferroni** — with ~47 genes, even descriptive per-gene CIs will look noisy. Pre-register the headline gene list (BRCA1, BRCA2, CFTR, HBB, plus the 4-6 highest-N rare genes) before looking at per-gene numbers, to avoid post-hoc cherry-picking.
6. **Backend 1 re-baseline** — the CPU baseline was measured on prompt v0.10 commit 85d1b34. Drift since then is plausible. Re-run baseline once at study start to confirm the 75/62/25 numbers still hold; if they don't, all paired tests rebase to the new number.
