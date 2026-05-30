# scripts/ — analysis + observability tools

22 scripts. Most read a `blinded_*.json` result file and emit a
specific diagnostic. None hit an LLM by default (the only LLM caller
is `rationale_judge.py`, which is explicitly opt-in).

Organized by when in the workflow you'd run them.

## Before launching a bench (preflight)

| Script | What it does |
|---|---|
| [`preflight.py`](preflight.py) | Runs pytest + benchmark lint + diversity + baselines. The one-line gate. |
| [`benchmark_lint.py`](benchmark_lint.py) | Schema + drug-name leakage check on every YAML case. Wired into CI. |
| [`dataset_diversity.py`](dataset_diversity.py) | Per-split distribution: target_kind, modality, therapeutic area. |

## During / right after a bench

| Script | What it does |
|---|---|
| [`regression_check.py`](regression_check.py) | Fails PR if dev or val recovery drops > tolerance vs `baselines.json`. |
| [`run_diff.py`](run_diff.py) | Per-case diff between two result JSONs (REGRESSED / RECOVERED / SOFT_CHANGE). |
| [`cross_run_agreement.py`](cross_run_agreement.py) | N-way per-case agreement across replicate runs of the SAME config. |

## Per-run diagnostics

| Script | What it does |
|---|---|
| [`miss_taxonomy.py`](miss_taxonomy.py) | Classifies misses: disease_gene_default / paralog_confusion / confabulation. |
| [`pattern_distribution.py`](pattern_distribution.py) | How often each Stage-1 pattern was picked. Flags Stage-1 collapse. |
| [`pattern_collapse_check.py`](pattern_collapse_check.py) | CI gate: fail if any pattern >60% or <3 distinct patterns. |
| [`pattern_correctness.py`](pattern_correctness.py) | For each miss: was it a Stage-1 (wrong pattern) or Stage-2 (right pattern, wrong target) error? |
| [`pattern_recovery_rate.py`](pattern_recovery_rate.py) | Per-pattern conditional recovery: which patterns is the agent good at? |
| [`rationale_pattern_check.py`](rationale_pattern_check.py) | Static check: does the predicted rationale contradict the picked pattern? |
| [`calibration.py`](calibration.py) | ECE + Brier + bin-by-bin gap. Is confidence trustworthy? |
| [`node_contribution.py`](node_contribution.py) | Per-node LLM-call counts + token economy hit/miss split. |

## Per-case explorers

| Script | What it does |
|---|---|
| [`explain_case.py`](explain_case.py) | One-page markdown explanation of any case (inputs, expected, predicted, verdict, trace). |
| [`evidence_report.py`](evidence_report.py) | Self-contained HTML with green/red per-case cards. Shareable. |

## Aggregating + comparing

| Script | What it does |
|---|---|
| [`frontier_plot.py`](frontier_plot.py) | ASCII Pareto frontier across runs (accuracy vs cost+wall). |
| [`sandbox_manifest.py`](sandbox_manifest.py) | Index every `blinded_*.json` in `sandbox/` into a markdown table. |
| [`full_review.py`](full_review.py) | Bundle headline + miss-taxonomy + pattern-dist + calibration + evidence-HTML into one markdown package. |

## Stats / planning

| Script | What it does |
|---|---|
| [`replicate_budget.py`](replicate_budget.py) | How many reruns to detect +N cases at alpha/power, given noise floor? |

## Opt-in LLM calls

| Script | What it does |
|---|---|
| [`rationale_judge.py`](rationale_judge.py) | Uses gpt-4o-mini to score rationale plausibility 0-3. Orthogonal to target_recovery. Cost ~$0.005/case. |

## Release / handoff

| Script | What it does |
|---|---|
| [`release_readiness.py`](release_readiness.py) | Pre-tag drift check (CHANGELOG freshness, markdown link integrity). |

## Conventions

- All scripts accept absolute or repo-relative paths.
- Scripts that read a result JSON tolerate the schema differences
  between runs at different versions (they'll silently skip fields
  introduced after the run was written).
- Scripts that emit markdown go to stdout by default. Redirect with `>`
  to capture.
- Exit code 1 from a script means a gate failed (lint / regression /
  collapse-check); exit code 0 means clean.
