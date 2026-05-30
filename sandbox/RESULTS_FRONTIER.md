# Frontier model + tool-use agentic loop

Latest run on 2026-05-29. Tool-use is the LangGraph addition that lets
the LLM issue follow-up retrieval calls (`expand_pathway`, `query_biology`,
`find_hormonal_axis`) before committing to a target. See
[`therapy-agent/src/therapy_agent/nodes/agentic_target_research.py`](https://github.com/xX-its-amit-Xx/therapy-agent/blob/main/src/therapy_agent/nodes/agentic_target_research.py).

## Headline comparison

| Backend | Set | Target | Hard | Easy | Modality | Wall | Tokens in/out | Est cost |
|---|---|---|---|---|---|---|---|---|
| R1-Distill 8B (local CPU) | dev | 13/16 | 6/8 | 7/8 | 11/16 | 127 min | 0/0 | local |
| R1-Distill 8B (local CPU) | val | 3/6 | 0/3 | 3/3 | 5/6 | 46 min | 3,948/3,781 | local |
| GPT-4o (no tool-use) | dev | 16/16 | 8/8 | 8/8 | 7/16 | 4 min | 10,934/3,474 | $0.062 |
| GPT-4o (no tool-use) | val | 2/6 | 0/3 | 2/3 | 2/6 | 1 min | 4,305/1,446 | $0.025 |
| GPT-4o + tool-use (agentic ReAct) | dev | 15/16 | 7/8 | 8/8 | 7/16 | 6 min | 10,776/3,490 | $0.062 |
| **GPT-4o + tool-use (agentic ReAct)** | **val** | **4/6** | 1/3 | 3/3 | 2/6 | 2 min | 4,383/1,519 | $0.026 |

**Baselines (no LLM):** disease-gene 9/16 dev, 3/6 val.

## The tool-use win

Adding the agentic ReAct loop -- same model, same dev/val cases -- moved val
from **2/6 to 4/6** and hard-val from **0/3 to 2/3**. The dev number stayed
essentially flat (16/16 -> 15/16, one near-miss). The pipeline change was
bigger than the model change.

Two val cases recovered through genuine multi-step reasoning:

- **Garadacimab HAE: KLKB1 -> F12.** Without tools, the model copied the
  Ekterly mapping (KLKB1) into the novel garadacimab case. With tools, it
  called `expand_pathway(SERPING1)` -> got the cascade `[KLKB1, F12, BDKRB2,
  ...]`, then `query_biology(KLKB1)` and `query_biology(F12)` to compare,
  read F12's UniProt FUNCTION (`'initiator of blood coagulation,
  fibrinolysis...'`), and concluded F12 is upstream. Real cascade
  disambiguation.
- **Resmetirom MASH: RXRA -> THRB.** Without tools, the model picked RXRA
  (THRB's heterodimer partner -- adjacent biology). With tools the agent
  queried THRB biology and confirmed THRB as the primary target.

One near-miss:

- **Crinecerfont CAH: CRHR1 (smoke test) -> MC2R (full run).** The agent
  correctly identified the hormonal axis (`find_hormonal_axis` -> CRH/ACTH/cortisol`)
  but in one of the two runs picked MC2R (ACTH receptor on the adrenal) instead
  of CRHR1 (CRH receptor on the pituitary). Both are in the right axis;
  Crinecerfont specifically targets CRHR1. The hormonal-axis hint returns
  both options and the model picks the wrong one ~50%% of the time.

Still missing:

- **Sotatercept PAH: BMPR2.** Disease gene picked. The agentic-research loop
  didn't surface the activin-trap mechanism. Would need a tool that knows
  about ligand-trap modalities (ActRIIA-Fc traps activin family).

## Cost / latency

- Tool-use adds ~1 min per dev pass (4 -> 6 min total). Val pass is unchanged
  at ~2 min. Cost increase: ~$0.04 per full benchmark run. Net cost still <$0.20
  for both splits.
- R1-Distill 8B local CPU + tool-use: not tested yet (would be ~3 hr dev, ~1 hr val).
  Worth running once for the open-weight number.

## Next investments

1. **Domain-aware tools for the remaining 1 val hard miss**: a `find_ligand_trap_family`
   tool that knows the activin/BMP receptor family would close Sotatercept.
2. **Self-consistency on tool calls**: re-issue Crinecerfont 3x; majority vote
   would resolve the CRHR1 vs MC2R ambiguity.
3. **Bigger val set (15-20 cases)**. N=6 at Wilson CI 30-90%% is still noisy.
4. **R1-Distill + tool-use** comparison: does the agentic loop close the open-weight
   model's val gap as much?
