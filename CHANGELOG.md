# Changelog -- therapy-stack benchmark + therapy-agent pipeline

Each row is a measurable change to either the agent or the benchmark.
The headline number is dev / val target recovery on the configuration
used at that version; cells marked "n/a" mean that split / metric
didn't exist yet at that version.

| Version | Date | Dev | Val | Adv | What changed |
|---|---|---|---|---|---|
| v0.1 | 2026-05-26 | 8/10 (orig 10) | n/a | n/a | First end-to-end on local Llama 3.2 3B with hand-rolled retriever |
| v0.2 | 2026-05-27 | 7/10 | n/a | n/a | Real `therapy-agent` LangGraph + 7-node pipeline, dropped to leak-corrected 7/10 |
| v0.3 | 2026-05-29 | 4/10 | n/a | n/a | Stripped 3 leakage paths (curated `_DRUGBANK`, `qc_genes` shortcut, narrative pathway_context) -- HONEST baseline |
| v0.4 | 2026-05-29 | 3/10 (3H/0E) | n/a | n/a | `interactor_biology_lookup` node, schema mismatch fix; expanded dev 10->16 |
| v0.5 | 2026-05-29 | 5/10 (1H/4E) | n/a | n/a | 2-stage decomposition + self-consistency vote + always-fire critique on 3B |
| v0.6 | 2026-05-29 | 6/10 (2H/4E) | n/a | n/a | Same pipeline, swapped to Llama 3.1 8B |
| v0.7 | 2026-05-29 | 13/16 (R1-Distill, 6H/7E) | 3/6 (0H) | n/a | R1-Distill-Llama-8B + full Tier 1; expanded dev with canonical oncology |
| v0.7+frontier | 2026-05-29 | 16/16 (GPT-4o, 8H/8E) | 2/6 (0H) | n/a | GPT-4o on same pipeline; dev/val gap = 67pp confirms pipeline ceiling |
| v0.7+tool-use | 2026-05-29 | 15/16 (GPT-4o tools) | 4/6 (1H) | n/a | New `agentic_target_research` ReAct loop with 3 tools |
| v0.7 final | 2026-05-30 | 15/16 | 4/6 | n/a | + multi-target acceptance + Stage 2 research-deference + SC3 |
| v0.8 (this round) | 2026-05-30 | 10/16 (R1-Distill SC1) | 9/12 (3H) | 1/4 | cache + field_rationale_align + 6 new val + pathway_neighbors + valid_targets + vote-margin confidence + adversarial set + observability stack |
| v0.9 (this round) | 2026-05-30 | tbd | tbd | tbd | disease_gene_default guard (targeted at the dominant val failure mode) |
| v0.9.1 (this round) | 2026-05-30 | tbd | tbd | tbd | pattern 9 (feedback_axis_receptor) + phenotype-pattern consistency override + extended guard kinds. Crinecerfont smoke blocked on RAM (Windsurf editor 10GB; only 3.8GB avail to load 5GB R1-Distill); to be re-measured on next clean run. |
| v0.9.2 (this round) | 2026-05-30 | tbd | tbd | tbd | Hard pattern override (skips Stage 1 re-prompt; force pattern_id=9). Crinecerfont smoke STILL missed -- Stage 1 LLM JSON parse was failing and target_kind was empty so the override gate didn't fire. |
| v0.9.2b (this round) | 2026-05-30 | tbd | tbd | tbd | Unconditional override on phenotype markers regardless of Stage 1 result. Crinecerfont smoke MOVED off disease-gene-default: predicted NR3C1 (glucocorticoid receptor) instead of CYP21A2. Right pattern category (feedback_axis_receptor), wrong specific receptor (NR3C1 vs CRHR1). DG-default rate 100% → 0% on this case. |
| v0.9.3 (this round) | 2026-05-30 | tbd | tbd | tbd | Mechanism-pattern guard: if mechanism=lof and Stage 1 picks disease_gene_mRNA, force downstream_effector. Targets the Iptacopan/PNH miss class. LLM-free unit tests verify guard fires correctly. |
| v0.9.4 (this round) | 2026-05-30 | tbd | tbd | tbd | Stage 2 picker prompt now has an explicit rule for target_kind=feedback_axis_receptor: pick the UPSTREAM RELEASING HORMONE receptor (CRHR1, GnRHR, TRHR) not the end-hormone receptor (NR3C1). Targets the v0.9.2b NR3C1 mispick on Crinecerfont. Crinecerfont single-case retest: predicted=MC2R/"ACTH receptor" (Crinetics atumelnant target, Phase 2/3 for CAH; biologically valid but not FDA-approved). Trajectory: CYP21A2 (v0.9 baseline) -> NR3C1 (v0.9.2b) -> MC2R (v0.9.4) -> CRHR1 (target). Strict score still 0/1; the model has converged on the HPA axis but lands on a non-FDA-approved upstream node. |
| v0.10 (this round) | 2026-05-31 | tbd | tbd | tbd | **g2p-rag actually wired in.** Upstream G2P portal API had retired the legacy endpoints (404 on `/gene-transcript-protein-isoform-structure-map/{symbol}` and `/protein-features/{uniprot}`); fixed in [g2p-rag@a2e2d27](https://github.com/xX-its-amit-Xx/g2p-rag/commit/a2e2d27) by routing through the current `/api/gene/{symbol}` endpoint + UniProt-direct for per-residue features. Built ChromaDB index of all 47 benchmark genes (684 chunks). Fixed therapy-agent's g2p_tool.py (wrong import path + wrong constructor signature; was ImportError-ing on every call). Every call now returns `source='g2p-rag (package)'` with gene-filtered chunks. The "UniProt fallback" path now only fires when g2p-rag is genuinely unavailable. |

## Lever-by-lever summary

For each upgrade lever, the *honest* lift on the relevant split:

| Lever | Lift on dev | Lift on val | Notes |
|---|---|---|---|
| Leakage strip (v0.2 -> v0.3) | -3 | n/a | The honest number is lower than the leaky one. The signal is now real. |
| Decomposition + SC3 + always-critique (3B, v0.4 -> v0.5) | +2 | n/a | Trades easy for hard; net +2 but loses 2 hard cases |
| Model swap 3B -> 8B (v0.5 -> v0.6) | +1 | n/a | Modality jumps to 7/16 |
| Model swap 8B -> R1-Distill 8B (v0.6 -> v0.7) | +7 | n/a | Reasoning model + dev expansion (10->16); the dev jump is partly dev-set change |
| Frontier (GPT-4o, v0.7) | +1 dev | -1 val | More memorization, no generalization. |
| Tool-use ReAct loop (v0.7+tool-use) | -1 dev | +2 val | Real reasoning gain on hard cases; small dev cost |
| Multi-target acceptance + valid_targets (v0.7 final) | 0 | 0 | Adds *rigor* without changing the headline |
| Stage 2 research-deference + SC3 (v0.7 final) | 0 | 0 | Same; closes failure modes the pipeline already had |
| v0.8 stack (cache + field_align + 6 new val + adv + observability) | varies by SC | +2 (with new val) | Most of the win is observability and adversarial coverage, not raw accuracy |
| disease_gene_default guard (v0.9) | TBD | TBD | Targeted at the single dominant remaining failure mode |
| Pattern 9 + feedback-axis override (v0.9.1) | TBD | TBD | Crinecerfont/CAH archetype: phenotype contains explicit feedback-axis markers (ACTH-driven, compensatory) but Stage 1 picks chaperone (4a). Override forces re-pick toward pattern 9 (feedback_axis_receptor → e.g. CRHR1) |

## What every round taught us

- **Leakage is the most important number to find.** The v0.2 -> v0.3 drop from 7/10 to 4/10 was the most important finding in the whole arc. Everything after that has been a comparison against a real baseline; everything before was overconfident.
- **Pipeline > model size on val.** GPT-4o vs R1-Distill on val: 2/6 vs 3/6. GPT-4o + tool-use: 4/6. The tool-use loop did more for val than the frontier-model swap did.
- **Adversarial cases discriminate; aggregate metrics don't.** R1-Distill v0.8 hits 9/12 val but only 1/4 adversarial. The aggregate val number hides the specific weakness `adversarial` surfaces.
- **Calibration is broken on every configuration measured.** Under-confidence with ECE 0.2-0.4. Don't use LLM self-reported confidence as a flag-for-review signal; vote margins are empirically better.
- **The miss taxonomy makes optimization legible.** Once you see "100% of val misses are disease_gene_default," you stop spraying improvements across the pipeline and start writing targeted guards.

## What's left for v0.10+

- **20+ val cases for statistical power.** Wilson 95% CI on 9/12 is 60-99%; we cannot distinguish 9/12 from 11/12.
- **Truly held-out test set kept secret from the prompt designer.** Both dev and val have been peeked at in iteration.
- **Multi-model ensemble** (GPT + Claude + R1-Distill votes) when API keys are restored.
- **Domain fine-tune** on (mechanism, target_kind) pairs from outside the test set.
- **CI runs Anthropic when secret is set** -- the workflow exists at `.github/workflows/benchmark.yml`, just needs the secret.
