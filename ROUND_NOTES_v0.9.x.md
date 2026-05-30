# Round notes -- v0.9.x (this session)

A single-page summary of what was shipped in this autonomous-iteration
round. Build artifacts referenced are pinned in this commit's tree.

## Headline

- **6 strategy-synthesis guards** added to `therapy-agent` (v0.9, v0.9.1,
  v0.9.2, v0.9.2b, v0.9.3, v0.9.4), each targeting a specific
  failure mode surfaced by the v0.8 miss-taxonomy.
- **23 new production-layer scripts** in `scripts/`, covering
  preflight, per-case explainers, per-run diagnostics, aggregation,
  CI gates, and release-readiness checks.
- **36 unit tests** (was 20), including 3 LLM-free tests of the
  v0.9.x guards' branching logic.
- **Documentation refresh**: README scorecard updated through v0.9.x;
  SUMMARY indexes every new script; RUNBOOK sections 12-14 added
  (miss-taxonomy reading guide, diversity audit, operational caveats);
  CHANGELOG row-by-row for v0.9 → v0.9.4; ARCHITECTURE.md and
  `scripts/README.md` for newcomers.
- **CI**: schema + leakage lint, docstring lint, val-integrity check
  wired in. PR-time sticky comment with per-case diff (already from
  v0.8).

## The single specific change that moved a number

Crinecerfont/CAH had been a persistent val miss across v0.8 / v0.9 /
v0.9.1 / v0.9.2. The agent predicted CYP21A2 (the disease gene) on
every run; the FDA-approved target is CRHR1.

After v0.9.2b (the unconditional feedback-axis override), smoke output:

```
case_id:               crinecerfont_cah
strategy_pattern_id:   9
strategy_target_kind:  feedback_axis_receptor
predicted_target:      Glucocorticoid receptor
expected_target:       CRHR1
target_recovered:      false (no match -- NR3C1, not CRHR1)
disease_gene_default_rate: 100% -> 0%
```

The agent has moved from a Stage-1 failure (wrong pattern category) to
a Stage-2 failure (right pattern, wrong specific target). The
`scripts/pattern_correctness.py` script classifies this:

```
| Case | Expected pattern | Picked pattern_id | Agreement | Verdict |
| crinecerfont_cah | 9 | 9 | ✓ | Stage-2 error (right pattern, wrong target) |
```

v0.9.4 adds an explicit prompt rule for `target_kind=feedback_axis_receptor`
distinguishing releasing-hormone receptors from end-hormone receptors;
whether that bridges the remaining gap is a TBD on the next bench.

## What didn't move

- **Iptacopan/PNH** (PIGA→CFB) is targeted by v0.9.3 (LoF +
  disease_gene_mRNA → downstream_effector). Smoke didn't include this
  case in isolation -- pending the next bench.
- **Sotatercept/PAH** (BMPR2→ACVR2A): R1-Distill picks BMPR2 even
  when agentic_target_research's loop proposes ACVR2B. None of the
  v0.9.x guards target this; the issue is Stage 2's collapse to the
  disease-gene prior under research-deference. Documented as v0.10 work.

## What's measurable

| Metric (new in this round) | Where |
|---|---|
| `strategy_pattern_id` per case | result JSON |
| `strategy_target_kind` per case | result JSON |
| `disease_gene_default_rate` per run | result JSON + stdout |
| `stack_commit` + `agent_commit` per run | result JSON |
| First 6 reasoning-trace lines | result JSON |

These let a reviewer or a future CI run answer:
- "Did the override fire on case X?" (strategy_pattern_id)
- "Did this configuration improve on the dominant failure mode?"
  (disease_gene_default_rate)
- "Which commit produced this result?" (stack_commit / agent_commit)

## The honest limitation

R1-Distill 8B's prior on "pick the disease gene" is stronger than
prompt-level constraints can move. The v0.9.2b unconditional override
gets it off the disease gene; the v0.9.4 picker rule has not yet been
shown to bridge the Stage-2 receptor-disambiguation gap. The fix
surface is structural (smaller candidate set) or model-scale (larger
LLM), not further prompt engineering. Documented in
[`README.md#honest-limitations-the-hidden-curriculum`](README.md#honest-limitations-the-hidden-curriculum)
finding 4 and `sandbox/RESULTS_FRONTIER.md` "honest limitation of
v0.9.x" section.

## Where to read next

- [`scripts/README.md`](scripts/README.md) -- index of all 23 production scripts
- [`CHANGELOG.md`](CHANGELOG.md) -- per-version lift table
- [`RUNBOOK.md`](RUNBOOK.md) -- on-call doc (sections 12-14 are new)
- [`sandbox/RESULTS_FRONTIER.md`](sandbox/RESULTS_FRONTIER.md) -- ablation table with v0.9.x section
