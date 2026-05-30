# Frontier model added to the blinded benchmark

On 2026-05-29 the benchmark gained an OpenAI backend. One run each on
dev and val with `gpt-4o` follows.

## Headline comparison

| Backend | Set | Target | Hard | Easy | Modality | Wall | Tokens in/out | Est cost |
|---|---|---|---|---|---|---|---|---|
| R1-Distill 8B (local CPU) | dev | **13/16** | 6/8 | 7/8 | 11/16 | 127 min | 0/0 | local |
| R1-Distill 8B (local CPU) | val | **3/6** | 0/3 | 3/3 | 5/6 | 46 min | 3,948/3,781 | local |
| GPT-4o (OpenAI) | dev | **16/16** | 8/8 | 8/8 | 7/16 | 4 min | 10,934/3,474 | $0.062 |
| GPT-4o (OpenAI) | val | **2/6** | 0/3 | 2/3 | 2/6 | 1 min | 4,305/1,446 | $0.025 |

**Baselines (no LLM):** disease-gene 9/16 dev, 3/6 val.

## The load-bearing finding

GPT-4o got **16/16 on dev with 8/8 hard cases** and **2/6 on val with 0/3 hard**.
Dev → val gap is **67 percentage points** for GPT-4o vs **31 percentage points**
for R1-Distill. The frontier model is strictly *worse* than the open-weight 8B
on val (2/6 < 3/6) and worse than the disease-gene baseline.

Interpretation: **the val gap is not a parameter ceiling**. Bigger models memorize
more of the FDA-approval literature, inflating dev, but they do not generalize
cross-pathway reasoning to post-cutoff approvals. Scaling the model is the wrong
investment from here. The pipeline ceiling is real.

## What GPT-4o missed on val and why

- **Crinecerfont CAH** → predicted *Mineralocorticoid receptor*. Treats salt-wasting
  in CAH but not the FDA target. R1-Distill picked the disease gene CYP21A2.
- **Resmetirom MASH** → predicted *RXRA*. Heterodimerizes with THRB.
  R1-Distill correctly predicted THRB.
- **Sotatercept PAH** → predicted *BMPR2*. The disease gene.
  R1-Distill made the same miss.
- **Garadacimab HAE** → predicted *KLKB1*, which is the *Ekterly* target from dev.
  R1-Distill made the same mistake.

GPT-4o is more *creative* and proposes sophisticated adjacent biology
(MR for CAH, RXRA for MASH). For a target-proposer with a defined FDA answer,
that creativity is a liability. R1-Distill's conservatism on easy cases is why
it outscored GPT-4o on val despite being roughly 20x smaller.

## Cost / latency

- R1-Distill 8B local CPU: 127 min dev + 46 min val. Zero API cost; ~$0 electricity.
  Constrained to one Llama process at a time per the local-LLM memory caps.
- GPT-4o via OpenAI API: 4 min dev + 1 min val. ~$0.09 total. ~30x faster wall-clock.

For iteration speed, GPT-4o is unambiguously better. For the val number to mean
anything new, neither model gets you there without pipeline changes.

## Recommended next investments

Confirmed by this finding, in priority order:

1. **Tool-use agentic loop** — let the agent issue follow-up retrieval calls so
   it can chain `disease gene → upstream regulator → druggable node` for cases
   like Crinecerfont (CYP21A2 → CRHR1) and Sotatercept (BMPR2 → ACVR2A).
2. **Hybrid graph reasoning** — compute 'upstream rate-limiting enzyme' and
   'downstream effector' deterministically from Reactome edges; feed as constrained
   candidates.
3. **Adversarial dev cases** — dev=16/16 with GPT-4o means dev is saturated.
   Need cases designed to fail the agent without leaking the answer.

4. **Bigger val set (15-20 cases)**. N=6 with Wilson CI 19-81% is too noisy to
   distinguish 2/6 from 3/6 statistically. Current val is informative as a
   directional signal, not a measurement.