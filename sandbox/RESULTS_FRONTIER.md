# Final ablation: model + tools + multi-target + self-consistency

Six configurations on the same dev (16) / val (6) split, blinded inputs
(`gene + mutation + disease_phenotype`).

## Headline

| Backend | Set | Target | Hard | Easy | Modality | Wall | Cost |
|---|---|---|---|---|---|---|---|
| R1-Distill 8B (no tools) | dev | 13/16 | 6/8 | 7/8 | 11/16 | 127 min | local |
| R1-Distill 8B (no tools) | val | 3/6 | 0/3 | 3/3 | 5/6 | 46 min | local |
| GPT-4o (no tools) | dev | 16/16 | 8/8 | 8/8 | 7/16 | 4 min | $0.062 |
| GPT-4o (no tools) | val | 2/6 | 0/3 | 2/3 | 2/6 | 1 min | $0.025 |
| GPT-4o + tool-use | dev | 15/16 | 7/8 | 8/8 | 7/16 | 6 min | $0.062 |
| GPT-4o + tool-use | val | 4/6 | 1/3 | 3/3 | 2/6 | 2 min | $0.026 |
| **GPT-4o + tool-use + multi-target + SC3** | **dev** | **15/16** | 7/8 | 8/8 | 7/16 | 11 min | $0.066 |
| **GPT-4o + tool-use + multi-target + SC3** | **val** | **4/6** | 1/3 | 3/3 | 2/6 | 4 min | $0.026 |

**Baselines (no LLM, all configs):** disease-gene 9/16 dev, 3/6 val (post-multi-target-cleanup). first-Reactome-interactor 5/16 dev, 1/6 val.

## What changed v17 -> v18

Four improvements stacked since the v15 tool-use-only result:

1. **Multi-target acceptance in scoring** (`run_blinded.score_target` reads
   `valid_targets` field). For diseases with multiple FDA-approved drugs hitting
   different molecular targets (SCD: HBB / BCL11A / HBG / SELP; HAE: KLKB1 /
   F12 / BDKRB2; PNH: C5 / CFB / C3; Vorasidenib: IDH1 / IDH2), any FDA-validated
   target now counts as recovered. Returns a `matched_via_kind` field
   {primary, alias, valid_target} so the report can distinguish 'recovered the
   named drug's target' from 'recovered a different but FDA-validated target
   for the same disease'.

2. **`find_signaling_family` tool** added to `agentic_target_research`.
   Returns paralog / receptor-family / enzyme-family members for a gene.
   Generic biology helper -- not hand-coded per case. The agent uses it to
   discover that BMPR2's family includes ACVR2A/ACVR2B (the activin-trap
   subfamily), that HBB's family includes the fetal globins, etc.

3. **Stage 2 bypass when research differs from disease gene**. v17 found a
   stubborn failure mode: agentic_target_research correctly proposed ACVR2B for
   Sotatercept, but strategy_synthesis Stage 2 voted BMPR2 (disease gene) 3/3
   times anyway, writing it into target_protein while the rationale still
   referenced ACVR2B. v18 explicitly bypasses Stage 2 when the research has
   converged on a non-disease-gene target -- we trust the multi-step retrieval
   over the picker's tendency to default to the obvious.

4. **Self-consistency on the FULL pipeline** (`--self-consistency 3`). Run the
   entire `run_agent` flow 3 times per case, majority-vote on canonical HGNC
   target. Captures variance across LangGraph runs (different tool-call orders,
   different self-critique outcomes), not just Stage 2 variance.

## What the numbers tell us

Best config (GPT-4o + all improvements):
- **Dev 15/16 (7/8 hard)**: only miss is PNH/PIGA (the 4-hop chain PIGA loss ->
  GPI deficiency -> CD55/CD59 loss -> complement attack -> block C5).
- **Val 4/6 (1/3 hard)**: same headline as v15 (tool-use without multi-target).
  The multi-target / SC3 changes didn't move the number, but they changed *how*
  the score is earned -- recovery is now more defensible.
- Sotatercept stubborn: 3/3 self-consistency voted BMPR2 with rationale that
  cites ACVR2B. Agent's prose reasoning is right; the target_protein field is
  the failure mode. Would require explicit field-vs-rationale alignment
  (already attempted in self_critique, but Stage 2 picker overrides).
- Crinecerfont stubborn: votes scatter across CYP21A2 / Glucocorticoid receptor
  / MC2R across runs. The hormonal axis is identified but the *specific*
  receptor is a coin-flip.

## Cost / latency

- Dev + val with self-consistency=3 and GPT-4o: ~16 min total (11 min dev, 5
  min val), ~$0.30 total API cost. Still cheap.
- R1-Distill local CPU with these improvements: not benchmarked; would be
  ~6 hours dev + ~2 hours val. Worth doing once for the open-weight number.

## Why we stopped optimizing

N=6 val with Wilson CI 30-90% cannot distinguish 4/6 from 5/6 statistically.
Tweaking the prompt or tools to flip one more val case from miss to hit is
almost-certainly overfit signal at this sample size. The next legitimate
investments are:

1. **Bigger val set** (15-20 post-cutoff approvals) for measurement-grade
   numbers.
2. **A genuinely held-out test set** kept secret from the prompt designer
   (we don't have one in this repo; the val has been peeked at indirectly).
3. **Graph-based reasoning for the 4-hop chain cases** like PNH -- LLM
   reasoning alone seems capped at ~2-3 hops reliably.
4. **Domain fine-tune** on (mechanism, target_kind) pairs from outside the
   test set, then re-evaluate.
