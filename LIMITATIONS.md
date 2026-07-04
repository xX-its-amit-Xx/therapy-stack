# Limitations

This project is useful as a reproducible therapeutic-strategy benchmark, but
the current evidence base is still small and iterative.

## Current Limits

- **Small N.** The current open-weight suite is 16 dev, 12 val, and 4
  attempted adversarial cases. Wilson intervals are wide; for example, 9/12
  val is 75% with a 95% CI of 47-91%.
- **Dev and val have both been peeked at.** Prompt and pipeline changes were
  informed by observed misses. Treat val as an iteration set, not a pristine
  held-out test.
- **No secret holdout split yet.** A truly held-out set that prompt designers
  cannot see is `NOT YET ESTABLISHED`.
- **Historical leakage incidents matter.** v0.2 -> v0.3 removed code/path
  leakage and lowered the honest dev score. v0.11 found prompt-level leakage
  in the CAH feedback-axis case; current prompts are sanitized and CI now runs
  `scripts/prompt_leakage_lint.py`.
- **Calibration is broken on measured configs.** LLM-reported confidence is
  not reliable enough to use as an operational review threshold.
- **GPT-4o numbers are likely contaminated by pretraining exposure.** Dev
  contains historically prominent FDA cases, so high dev scores should not be
  interpreted as generalization.
- **Existing historical JSON lacks full provenance.** Older result files did
  not record run date, `therapy-agent` commit, or `g2p-rag` commit. The ledger
  marks those fields as `NOT RECORDED IN SOURCE FILE`; new runs written by
  `sandbox/run_blinded.py` include them.

## Publication Rule

Any public number must be generated from a committed result artifact and
listed in [`results/ledger.json`](results/ledger.json), or visibly marked
`NOT YET MEASURED`.
