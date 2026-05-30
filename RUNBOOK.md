# Runbook -- therapy-stack benchmark in production

Treat this file as the on-call doc. Production teams iterating on the agent
or its prompts should be able to (a) reproduce a benchmark run, (b) decide
whether a change is safe to ship, and (c) recover from common failure
modes -- all from what's in this file.

## 1. Splits

| Split | Where | Use |
|---|---|---|
| **dev** (16 cases) | `therapy-agent/benchmarks/{*.yaml, cases/*.yaml}` | Iterate prompts and retrieval here. Score on every PR. Overfitting risk is real -- treat dev as a fitness function, not a ground truth. |
| **val** (6 cases) | `therapy-agent/benchmarks/heldout_2024_2025/*.yaml` | Post-2024 FDA approvals, after every current open-weight model's training cutoff. **Never touch a val case in response to a result.** Touching val invalidates it for the rest of the quarter. |
| **all** | dev + val | Use only for final reporting in releases. |

## 2. Running locally

```powershell
cd sandbox
$env:THERAPY_AGENT_LLM_BACKEND = "llama"
$env:LLAMA_MODEL_PATH = "C:/llama-models/DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"

# Dev iteration loop (~80 min on 8-core CPU with R1-Distill 8B):
./.venv/Scripts/python.exe run_blinded.py --set dev --out dev_results.json

# Honest generalization number (~30 min):
./.venv/Scripts/python.exe run_blinded.py --set val --out val_results.json

# Smoke baselines only (~1 min):
./.venv/Scripts/python.exe run_blinded.py --set all --baselines-only
```

## 3. Running in CI

`.github/workflows/benchmark.yml` runs on every PR touching `sandbox/**`
and on every push to `main`. It does two jobs:

- **smoke**: 5-min job, no LLM. Validates that the YAML benchmarks parse,
  the harness imports cleanly, and the baselines compute. Always runs.
- **benchmark**: 30-min job using Claude via the Anthropic SDK. Only runs
  if the `ANTHROPIC_API_KEY` repository secret is set. Calls
  `scripts/regression_check.py` to gate the PR against `baselines.json`.

To run a one-off cloud benchmark on demand, use the `workflow_dispatch`
trigger with the `set` input. Artifacts (`dev_results.json`,
`val_results.json`) are uploaded with 30-day retention.

## 4. The regression check, formally

`scripts/regression_check.py` reads `baselines.json` and fails if:

- **Recovery drop**: dev or val target_recovered is more than `--tolerance`
  cases below the locked baseline (default 1 case).
- **Hard-case drop**: hard-case recovery (target != disease gene) drops
  below the locked baseline by more than `--tolerance`.
- **Cost regression**: total wall time exceeds the locked ceiling by >25%.

When a regression check fails, **the right response is almost never to bump
the lockfile**. Investigate the rationale changes in
`predicted_rationale` per case, then either fix the prompt change or back
it out.

A baseline bump is acceptable when:
1. The drop is offset by a documented gain on the OTHER split (dev down 1,
   val up 2), and
2. The reviewer signs off explicitly, and
3. The notes field in `baselines.json` explains why.

## 5. Local LLM operations

See `.claude/.../memory/local_llm_memory_caps.md` (this user's machine):

- One Llama process at a time. Never run two benchmarks concurrently --
  CPU contention + RAM pressure can OOM.
- `n_ctx = 8192`. Don't raise to the model's `n_ctx_train`; the KV cache
  scales linearly with context length.
- Q4_K_M quants. ~2 GB for 3 B, ~5 GB for 8 B.
- Sequence model swaps -- the prior `Llama` instance must fall out of
  scope before launching the next benchmark.

## 6. Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `FileNotFoundError: therapy-agent` | sibling repo not on disk next to `therapy-stack` | `git clone` it next door, or set `THERAPY_AGENT_ROOT` |
| Llama loads then run dies silently | D: drive full (results JSON can't write) | free disk (`du -sh` AppData/Local subdirs) |
| All cases miss with `pred=""` | Stage 1 pattern selector JSON truncated at max_tokens | `_close_unbalanced_braces` should auto-repair; if it doesn't, raise `max_tokens=400` in `_select_pattern` |
| Self-consistency picks degenerate `[]` | Llama generated invalid JSON 3/3 times | check temperature; should be 0.5, not 0; verify `n_ctx` is high enough |
| Anthropic 429 in CI | rate-limit | retry-with-backoff already wired via `tenacity`; if persistent, downgrade `ANTHROPIC_MODEL` or batch with delays |
| Modality score = 0 across the board | crosswalk in `score_modality` missed the new modality string | add the synonym to the `classes` dict in `run_blinded.score_modality` |

## 7. What's NOT in scope

This runbook covers the BENCHMARK pipeline. The actual agent
(`therapy-agent`) has its own runbook for production deployment --
monitoring, prompt versioning in a registry, A/B tests, sampled human
review of production traces, alerting on accuracy drift. Those are real
production concerns; this repo is the evaluation harness, not the
serving layer.

## 8. Quarterly rotation

- **End of quarter**: refresh `benchmarks/heldout_2024_2025/` with FDA
  approvals from the *next* quarter that the current models couldn't
  have seen. Rename the directory to reflect the new cutoff window.
  Re-score all configs against the new val set.
- **The current val cases** then graduate into dev and are no longer
  held out. This is the only legitimate way to "use" val data.

## 9. Provenance and audit

Every PR's CI run uploads `dev_results.json` and `val_results.json` as
GitHub artifacts with 30-day retention. To audit a historical claim
("the 13/16 number from commit X"), pull the matching artifact.

## 10. Observability tools (v0.8+)

Beyond regression_check, the repo ships three orthogonal analysis tools:

- **`scripts/run_diff.py`** -- side-by-side per-case diff between two
  result JSONs. Headline: `DIFF: +N cases | regressed=A recovered=B ...`.
  Used in CI to post a sticky PR comment showing exactly which cases
  changed. Exit code 1 if any regressions found (intended for CI
  gating).

- **`scripts/calibration.py`** -- Expected Calibration Error + Brier
  + bin-by-bin gap analysis. Tells you whether the agent's confidence
  tracks accuracy. Current finding (v0.8): the agent is consistently
  UNDER-confident (claims ~0.3, recovers ~86%); confidence should not
  be used as a "flag for human review" gate.

  When `--self-consistency >= 2` is used at run time,
  `strategy.confidence_score` is REPLACED with the vote margin
  (winner_votes / n_samples), which is empirically better calibrated.
  `strategy.confidence_source = "vote_margin(2/3)"` carries provenance.

- **`scripts/rationale_judge.py`** -- LLM-as-judge for rationale
  plausibility (0-3 scale: contradicts / irrelevant / adjacent /
  canonical). Orthogonal to target_recovery. Useful for surfacing
  agent confabulation and for finding "agent picked a defensible
  target the YAML didn't list" cases. Cost ~$0.005 per case on
  gpt-4o-mini; run on demand, not every PR.

The intent: target_recovery is the headline metric; calibration,
plausibility, and per-case diffs are the diagnostic signals a
production team needs to know WHY a number changed.

## 11. Adversarial test set (`benchmarks/adversarial/`)

In addition to dev and val, the adversarial set holds cases hand-crafted
to fail an agent that has the wrong inductive bias on a documented
failure mode (paralog confusion, lazy multi-target acceptance,
field-rationale decoupling, etc.). Each case has a NARROW
`valid_targets` set and the phenotype framing is engineered to make
naive-default answers wrong.

Adversarial scores are tracked SEPARATELY from dev/val (different
curation philosophy; don't aggregate). A drop in adversarial recovery
is a signal that a recent change weakened a specific behavior; cross-
reference with the failure mode the case was designed to probe.

## 12. Reading a miss: the failure-mode taxonomy

When a case misses, `scripts/miss_taxonomy.py` classifies it into one of:

| Failure mode | Heuristic | What to do |
|---|---|---|
| `disease_gene_default` | predicted = disease gene, expected ≠ disease gene | The Stage 1 pattern selector chose a non-disease-gene pattern but Stage 2 still output the disease gene. The v0.9 guard catches this for {downstream_effector, paralog, upstream_enzyme, cargo_receptor, downstream_receptor_agonist, repressor, feedback_axis_receptor}. If the miss is in a *disease-gene-centric* pattern (chaperone, mRNA), check the v0.9.1 feedback-axis override -- the phenotype may need a feedback marker that's not yet in the marker list. |
| `paralog_confusion` | predicted is in the same biology-curated family as the expected target or disease gene | The agent picked a sibling. Often a real biology-class match (CHRM5 vs CHRM4). If the YAML's `valid_targets` doesn't cover the sibling, decide whether to broaden the set (multi-target acceptance is legitimate) or leave it strict (some siblings really are wrong). |
| `confabulation_off_pathway` | predicted is in neither the disease gene's family nor the expected target's family | The retrieval stack didn't deliver the right candidates. Check the `pathway_genes` and `interactor_text` blocks in the agent state for the case. Likely needs a curated `pathway_neighbors` lookup or an explicit `agentic_target_research` tool call. |
| `no_prediction` | predicted_target is empty | The agent fell back to "Unknown" -- usually an LLM JSON parse failure or a backend error. Check the run log. |

A successful production iteration moves cases from `confabulation_off_pathway` → `paralog_confusion` → `disease_gene_default` → recovered, in roughly that order: first you fix retrieval, then you fix family-disambiguation, then you fix the disease-gene-default lazy fallback, and only then is the residual miss "real" pipeline failure.

The disease-gene-default rate is also surfaced in every `blinded_*.json` as
`disease_gene_default_rate` (and the underlying counts). When this is > 0.2
on val, the disease-gene-default guard is not pulling its weight and a
prompt-level change is warranted before any other optimization.

## 13. Dataset diversity audit

`scripts/dataset_diversity.py` reports the dev/val/adversarial splits by
target_kind, modulation_type, and therapeutic area. A split that's 80%
inhibitors-against-disease-gene is a different benchmark than one
spread across modalities. The current state (`sandbox/DIVERSITY.md`):

- dev: 56% disease_gene, 38% downstream_effector, 6% paralog
- val: 50% disease_gene, 50% downstream_effector
- adv: 43% disease_gene, 57% downstream_effector (the adversarial set
  is deliberately biased toward the harder case)

If you add a benchmark case, regenerate the diversity report. A val
that's drifted to 80% disease_gene would let the disease-gene-default
agent cheat the headline number; the adversarial set is the guard
against that drift.

## 14. Operational notes

- **One Llama process at a time.** The local-Llama backend mmaps a
  ~5 GB GGUF; running two concurrent instances OOMs on 64 GB CPU-only
  with the rest of the agent stack loaded. The CI workflow uses the
  Anthropic backend for this reason.
- **The val set has been peeked at.** Each case has been examined when
  it failed; this is honest curator iteration but it does mean val is
  not a clean held-out set anymore. The proper held-out set is the
  *next quarter's* FDA approvals (section 8).
- **No commits during a bench run.** A model load takes ~15 sec; if a
  rebase or branch switch lands during the load, the run will fail
  midway and produce a half-populated JSON. Run benches against a
  clean working tree.
