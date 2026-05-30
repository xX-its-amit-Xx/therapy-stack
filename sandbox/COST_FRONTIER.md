# Cost-vs-accuracy frontier across configurations

Generated from the blinded_v*.json result files in this directory.
Cost is OpenAI API cost ($2.50/M in, $10.00/M out for gpt-4o); local
Llama runs are $0 but pay a wall-clock tax.

## TL;DR for the cost-conscious reader

- **Best dev accuracy/$:** GPT-4o, $0.06, 4 min, 16/16 (100%).
- **Best val accuracy/$:** R1-Distill 8B local, $0, 99 min, 9/12 (75%).
- **No frontier domination across backends.** Local-Llama beats GPT-4o
  on val (75% vs 67%) but loses on dev (62% vs 100%). The dev/val gap
  isolates *retention* (does the model recognize cases it has seen in
  pretraining?) from *generalization* (does the pipeline carry an
  unfamiliar case?).

## Per-split breakdown

The frontier should be read per split, since dev and val have
different distributions (dev: 16 cases of historically-prominent
FDA targets; val: 12 post-2024 NMEs, post pretraining cutoff for
most public models).

### dev (16 cases, historically prominent targets)

| Run | Backend | Acc | Wall (min) | Est cost |
|---|---|---|---|---|
| `blinded_v14_dev_gpt4o` | gpt-4o | 16/16 (100%) | 4.0 | $0.062 |
| `blinded_v16_dev_gpt4o_tools` | gpt-4o + ReAct | 15/16 (94%) | 5.7 | $0.062 |
| `blinded_v18_dev` | gpt-4o full pipeline | 15/16 (94%) | 11.0 | $0.066 |
| `blinded_v11_expanded` | R1-Distill local | 12/16 (75%) | 126.6 | $0 |
| `blinded_v20_dev_llama` | R1-Distill local + cache | 10/16 (62%) | 147.8 | $0 |

The drop from `v11_expanded` (12/16) to `v20_dev_llama` (10/16) is a
real regression and the v0.9 round was specifically built to recover
that ground (see `RUNBOOK.md` section 11 and the regression check in
CI).

### val (12 post-2024 NMEs)

| Run | Backend | Acc | Wall (min) | Est cost |
|---|---|---|---|---|
| `blinded_v20_val_llama` | R1-Distill local + full pipeline | 9/12 (75%) | 99.0 | $0 |
| `blinded_v17_val_sc3` | gpt-4o + SC3 | 4/6 (67%) | 5.5 | $0.024 |
| `blinded_v18_val` | gpt-4o + tools + SC3 + field_align | 4/6 (67%) | 4.2 | $0.026 |

Note that the GPT-4o runs were against the first 6 val cases only
(SCD, HAE, AAV-Hem A, Sotatercept-PAH, NTLA-2002, GLP1-NASH); the
R1-Distill run got the expanded 12-case val (+donanemab, +iptacopan,
+lebrikizumab, +aprocitentan, +capivasertib, +cobenfy).

### adversarial (7 hand-crafted probes; only 4 attempted so far)

| Run | Backend | Acc | Wall (min) | Est cost |
|---|---|---|---|---|
| `blinded_v20_adv_llama` | R1-Distill local | 1/4 (25%) | 39.9 | $0 |

The adversarial set is where headline numbers stop being meaningful.
75% val for the same config drops to 25% adv -- the cases probe
specific failure modes (paralog confusion, cascade-branch choice,
field-rationale decoupling) and 3 of those failure modes survive the
v0.8 pipeline.

## How to interpret this frontier

1. **The headline number is split-conditional.** Picking the
   "best config" by a single accuracy number is wrong if you don't
   say which split. `v14_dev_gpt4o` 100% is honest for dev; it would
   be misleading shorthand for "best on val too."

2. **Local Llama is on the val frontier for free.** The val gap
   between GPT-4o and R1-Distill 8B is not a model-capacity ceiling
   -- it's a pipeline ceiling. The same pipeline runs both. The
   thing that moves val is `agentic_target_research` + ReAct + the
   pathway expansion stack, not the LLM choice.

3. **Wall time matters in CI.** A 100-min R1-Distill run is too slow
   for per-PR CI. The CI workflow uses Anthropic Claude (via
   `ANTHROPIC_API_KEY` secret) for speed; local Llama is for the
   research workflow.

4. **Cost is not a knob in the no-LLM baseline.** The
   `disease-gene-default` baseline (in `baselines.json`) is $0 and
   instant. The gap between baseline and best agent is the
   *agent-attributable* lift; it's what's at stake when we shop a
   configuration change.

## Limitations of this comparison

- **Different N across val runs** -- 6 vs 12 cases means the val
  numbers are not directly comparable across columns. The 4/6 GPT-4o
  number predates the val expansion.
- **No retry / variance bands.** Each config ran once. SC3
  internally votes 3 times, but the wall-clock-vs-accuracy point on
  the chart is one realization. A future run should bootstrap +
  variance.
- **Cost estimate uses summed tokens, not per-case rates.** Rough
  but adequate for budgeting.
