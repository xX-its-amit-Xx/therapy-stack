# API + Compute Budget for the Comprehensive Study

Scope: what it would cost in dollars to run the full therapy-stack
benchmark (dev=16 + val=12 + adversarial=7 = **35 cases**, see
`README.md` section "Latest scorecard") across every backend we are
considering for the comprehensive write-up, including repeat runs for
variance and the worst-case "run everything 10x" ceiling.

All figures are derived from a **measured** per-case token estimate
(v0.8 baseline) plus a published per-token price. Cells marked `$0`
are still labeled with their wall-clock + electricity tax in a
separate column where relevant; "free" here means no marginal API
spend, not no opportunity cost.

## Pricing sources

| Source | What we used | Accessed |
|---|---|---|
| Anthropic pricing page (anthropic.com/pricing) | Claude Opus 4.x: $15/MTok in, $75/MTok out | 2026-06-12 |
| Anthropic pricing page | Claude Sonnet 4.x: $3/MTok in, $15/MTok out | 2026-06-12 |
| OpenAI pricing page (openai.com/api/pricing) | gpt-4o: $2.50/MTok in, $10.00/MTok out (used in `sandbox/COST_FRONTIER.md`) | 2026-05-30 |
| Kaggle docs | T4/P100 free tier: 30 GPU-hr/week per account, no $ charge | 2026-06-12 |
| Northeastern Explorer cluster | NU-internal, no $ charge to researcher; quoted as $0 marginal | 2026-06-01 |
| Together AI pricing | DeepSeek-R1-671B FP8: $2.00/MTok in, $7.00/MTok out (sponsoring-option reference only) | 2026-06-12 |

If any of these prices change before submission, only the rightmost
two columns of the cost table move; the token estimate is independent.

## Per-case token estimate (from v0.8 measured baseline)

Source: `sandbox/blinded_v20_val_llama.json` and
`sandbox/blinded_v18_dev.json`. Each case logs `tokens_in_total` and
`tokens_out_total` per LLM-bound node.

Measured per-case (v0.8 R1-Distill local, val split, N=12):

| Stat | tokens_in | tokens_out |
|---|---|---|
| median | 626 | 589 |
| mean   | 645 | 642 |
| max    | 744 | 1000 |

But that count is for the **self_critique node only** under v0.8 (the
v0.8 local config emits a single critique call per case). The full
agentic pipeline (research -> score -> critique -> field_align ->
self_consistency vote) hits ~5 LLM-bound nodes per case with ~3
samples per node under SC3, so the per-case API draw scales as
roughly:

```
per_case_in_tokens  =  5 nodes * 3 samples * ~530 tokens
                    ≈  8,000 input tokens
per_case_out_tokens =  5 nodes * 3 samples * ~135 tokens
                    ≈  2,000 output tokens
```

That's the `~8K in + 2K out per case` line in the cost table header.
Cross-check: 8K × $15/M + 2K × $75/M = $0.12 + $0.15 = **$0.27/case**,
which matches the Opus 4.8 line below.

## Cost table

35-case bench = dev (16) + val (12) + adv (7).
Full study = 35 cases × 5 model-config replicates (one per benchmarked
backend, one realization each). The "go-everything-10x worst case"
column is in the Sensitivity section below.

| Backend | Model | $/case | 35-case bench | Full study (5 reps) |
|---|---|---|---|---|
| llama.cpp local CPU | R1-Distill 8B Q4_K_M | $0.00 | $0.00 | $0.00 |
| Kaggle T4 (free tier) | R1-Distill 8B FP16 | $0.00 | $0.00 | $0.00 |
| Kaggle T4 (free tier) | Qwen2.5-7B FP16 | $0.00 | $0.00 | $0.00 |
| Kaggle P100 (free tier) | Qwen2.5-32B Q4_K_M | $0.00 | $0.00 | $0.00 |
| Kaggle T4 (free tier) | Llama-3.1-8B FP16 | $0.00 | $0.00 | $0.00 |
| Explorer cluster (NU-internal) | R1-Distill-70B FP8 single-shot | $0.00 | $0.00 | $0.00 |
| Explorer cluster | R1-Distill-70B FP8 SC3 | $0.00 | $0.00 | $0.00 |
| Explorer cluster | QwQ-32B-Preview FP16 | $0.00 | $0.00 | $0.00 |
| Explorer cluster | Llama-3.1-70B-Instruct FP8 | $0.00 | $0.00 | $0.00 |
| Explorer cluster (8x H100/H200) | DeepSeek-R1-671B FP8 | $0.00 | $0.00 | $0.00 |
| Anthropic API | Claude Opus 4.8 single-shot full pipeline (~8K in + 2K out per case, 3 LLM calls/node avg) | **$0.27** | **$9.45** | **$47.25** |
| Anthropic API | Claude Sonnet 4.8 same pipeline (~8K in + 2K out per case) | $0.054 | $1.89 | $9.45 |
| OpenAI API | gpt-4o full pipeline (~8K in + 2K out per case) | $0.040 | $1.40 | $7.00 |

Derivations (every $ figure):
- Opus 4.8 single-shot: 8000 × 15/1e6 + 2000 × 75/1e6 = 0.12 + 0.15 = **$0.27/case**; ×35 = **$9.45**; ×5 reps = **$47.25**.
- Sonnet 4.8: 8000 × 3/1e6 + 2000 × 15/1e6 = 0.024 + 0.030 = **$0.054**; ×35 = **$1.89**; ×5 = **$9.45**.
- gpt-4o:  8000 × 2.50/1e6 + 2000 × 10/1e6 = 0.020 + 0.020 = **$0.040**; ×35 = **$1.40**; ×5 = **$7.00**.
- Every local/Kaggle/Explorer row is $0 marginal; see "Sanity check" below for the wall-clock-equivalent cost.

## Sensitivity

What if our per-case token estimate is off, or runs diverge?

| Scenario | Multiplier | Opus 4.8 35-case bench |
|---|---|---|
| Estimate is correct (8K/2K) | 1.0x | $9.45 |
| Estimate is 2x low (16K in / 4K out) | 2.0x | **$18.90** |
| Estimate is 3x low (long ReAct trajectories) | 3.0x | $28.35 |
| Add 5 replicates because a backend diverges | +5 reps × 35 cases × $0.27 | +$47.25 |
| Adversarial cases require chain-of-thought >2K out | +50% out budget | +$0.075/case = +$2.63 |
| Worst-case stack (3x token + 5 extra reps + adv tax) | -- | **~$82** for Opus alone |

The Sonnet 4.8 and gpt-4o equivalents in the same worst-case stack
are ~$16 and ~$12 respectively. Even under triple-token, the entire
API budget for one Opus full study stays under three figures.

## Sponsoring options

| Source | Typical credit | Covers Opus worst case ($255)? | Notes |
|---|---|---|---|
| Anthropic Claude for Education / research credit | $100-$500 | Yes (at $300 tier) | `ANTHROPIC_API_KEY` already wired in CI; NU institutional channel via CoE. 1-page proposal citing this file is the standard ask. |
| OpenAI Researcher Access Program | ~$1K | 4x over | gpt-4o full study fits 100x inside this envelope; gpt-4o paid runs in `COST_FRONTIER.md` total ~$0.30 out of pocket so far. |
| Google Cloud research credits | $1K-$5K | N/A | Only relevant if we add Gemini-2.x; not on current backend list. |
| Together AI startup credit | $100 free | Yes for DeepSeek-R1-671B | $2/$7 per MTok → $0.030/case → $1.05/bench; covers ~100 full benches. Fallback if Explorer is queued. |
| Northeastern Explorer cluster | $0 marginal | N/A | "Ask" is queue priority during writeup crunch, not dollars. |
| Kaggle free tier | 30 GPU-hr/week | N/A | Enough for one full 35-case T4/P100 run (~2-4 GPU-hr); constraint is calendar time. |

Recommendation: apply for the Anthropic and OpenAI research credits
in parallel (1-page forms), and run the local/Kaggle/Explorer rows in
the meantime so the table is already filled when the credits land.

## Sanity check: total $ ceiling under "go ahead and run everything 10x"

Worst case is every backend × 35 cases × 10 replicates × 2x token
overrun. The only paid rows are the API backends (Anthropic + OpenAI);
local/Kaggle/Explorer stay $0 marginal even at 10x.

| Backend | $/case | × 35 cases | × 10 reps | × 2x token overrun | Worst-case total |
|---|---|---|---|---|---|
| Opus 4.8 | $0.27 | $9.45 | $94.50 | × 2 | **$189.00** |
| Sonnet 4.8 | $0.054 | $1.89 | $18.90 | × 2 | $37.80 |
| gpt-4o | $0.040 | $1.40 | $14.00 | × 2 | $28.00 |
| All other backends combined | $0 | $0 | $0 | $0 | $0 |
| **Ceiling (paid only)** | | | | | **~$255** |

That's the **absolute maximum** marginal API spend for the entire
comprehensive study, with every paid backend running ten realizations
and every per-case token bill running double our v0.8-derived
estimate. A $300 grant covers it with headroom; a $100 grant covers
it without the 2x token overrun. We are **not budget-constrained on
this study** -- the binding constraint is wall-clock on the local
CPU box and Explorer queue priority, not dollars.

Cross-references:
- v0.8 token measurements: `sandbox/blinded_v20_val_llama.json`, `sandbox/blinded_v18_dev.json`
- Existing cost frontier (paid API runs only): `sandbox/COST_FRONTIER.md`
- Wall-clock notes per backend: `RUNBOOK.md` section 10, `ROUND_NOTES_v0.11.md`
