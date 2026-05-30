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
