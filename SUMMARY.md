# therapy-stack -- portfolio summary

A blinded benchmark for drug-target prediction agents. Inputs are
`gene + mutation + disease_phenotype` only; the agent must propose a
therapeutic target without ever seeing FDA drug or target names.

## The headline numbers (best config, GPT-4o + v0.7 pipeline + SC=3)

| Split | Cases | Recovered | Notes |
|---|---|---|---|
| **dev** | 16 | 15/16 (94%) | The number to take with a grain of salt -- model has read these |
| **val** | 6 -> 12 (post-2024 NMEs) | 4/6 -> 9/12 with multi-target | Honest generalization signal |
| **adversarial** | 7 | 1/4 (so far) | Cases hand-crafted to fail specific failure modes |

**Baselines** (no LLM): disease-gene-default on dev 9-10/16, val 3-8/12.

Best result on a fully open-weight stack (R1-Distill 8B local CPU,
no API key): **dev 13/16, val 9/12** with multi-target.

## What it actually is

A retrieval-augmented FDA-target *explainer* for known biology, not a
novel-target *discoverer*. The agent:

1. Loads a LangGraph (`therapy-agent`) with 9 nodes covering parse ->
   variant lookup -> mechanism classify -> pathway expand -> druggability
   -> interactor biology -> agentic ReAct research -> strategy synthesis
   (2-stage decompose + 3x self-consistency) -> field-rationale align ->
   self-critique.
2. Hits real public APIs at every retrieval step: UniProt, Reactome
   ContentService, ChEMBL, ClinVar. Cached at 300s TTL.
3. Backend-agnostic LLM layer (`therapy_agent.llm`): Anthropic, OpenAI,
   or local llama-cpp behind one Anthropic-shape adapter.
4. Scored against the curator-defined `target_protein` AND a per-disease
   `valid_targets` superset of FDA-validated alternatives, so SCD (HBB
   stabilizer vs BCL11A enhancer disruption) and HAE (KLKB1 vs F12 vs
   BDKRB2 inhibitors) don't get penalized for picking the wrong one of
   several correct answers.

## What's honest about the numbers

Every caveat in [`README.md`](README.md#honest-limitations-the-hidden-curriculum)'s
"Honest limitations" section applies. Most importantly: **N=22 across
splits is too small for any single number to be statistically
distinguishable from a one- or two-case noise drift.** Wilson 95% CI on
9/12 val is 55-95%.

The signal that survives the small-N caveat:

- **GPT-4o vs R1-Distill 8B on val: comparable** (2/6 vs 3/6 without
  tools; 4/6 vs same with tools). The val gap is a *pipeline* ceiling,
  not a model-size ceiling.
- **Tool-use loop is the biggest single lever**: 2/6 -> 4/6 val with
  no model change.
- **Adversarial set discriminates**: configurations that score equally
  on val score differently on adversarial.
- **Calibration is broken on every config measured**: ECE 0.2-0.4,
  under-confident. Vote margins from self-consistency are better
  calibrated.

## Production layer (`.github/workflows/benchmark.yml` + scripts/)

| What | What it does |
|---|---|
| [`baselines.json`](baselines.json) | Frozen scorecard the regression check gates against |
| [`scripts/regression_check.py`](scripts/regression_check.py) | Fails PR if dev or val recovery drops > tolerance |
| [`scripts/run_diff.py`](scripts/run_diff.py) | Per-case CI diff (REGRESSED / RECOVERED / SOFT_CHANGE) |
| [`scripts/calibration.py`](scripts/calibration.py) | ECE + Brier + bin-by-bin gap |
| [`scripts/rationale_judge.py`](scripts/rationale_judge.py) | LLM-as-judge for rationale plausibility (orthogonal to target recovery) |
| [`scripts/miss_taxonomy.py`](scripts/miss_taxonomy.py) | Classifies misses by failure mode (disease_gene_default / paralog / confabulation) |
| [`scripts/frontier_plot.py`](scripts/frontier_plot.py) | ASCII Pareto frontier across runs (acc vs cost+wall) |
| [`scripts/benchmark_lint.py`](scripts/benchmark_lint.py) | Schema + drug-name leakage check on YAML cases (CI gate) |
| [`scripts/dataset_diversity.py`](scripts/dataset_diversity.py) | Per-split target_kind / modality / area distribution |
| [`scripts/evidence_report.py`](scripts/evidence_report.py) | Self-contained HTML per-case evidence cards |
| [`scripts/explain_case.py`](scripts/explain_case.py) | One-page markdown explanation of any single case |
| [`scripts/pattern_distribution.py`](scripts/pattern_distribution.py) | Stage-1 pattern picks across a run (flags pattern collapse) |
| [`scripts/pattern_collapse_check.py`](scripts/pattern_collapse_check.py) | CI gate: fail if any Stage-1 pattern dominates >60% |
| [`scripts/rationale_pattern_check.py`](scripts/rationale_pattern_check.py) | Static check: rationale text consistent with picked pattern |
| [`scripts/node_contribution.py`](scripts/node_contribution.py) | Per-node LLM-call + token economy (hit/miss split) |
| [`scripts/preflight.py`](scripts/preflight.py) | One-line gate: pytest + lint + diversity + baselines before a bench |
| [`scripts/release_readiness.py`](scripts/release_readiness.py) | Pre-tag drift check (CHANGELOG freshness, markdown link integrity) |
| [`scripts/sandbox_manifest.py`](scripts/sandbox_manifest.py) | Index of every `blinded_*.json` + companion report |
| [`sandbox/DIVERSITY.md`](sandbox/DIVERSITY.md) | Latest dataset diversity snapshot |
| [`sandbox/COST_FRONTIER.md`](sandbox/COST_FRONTIER.md) | Latest cost-vs-accuracy frontier |
| [`sandbox/MANIFEST.md`](sandbox/MANIFEST.md) | Latest index of result files + reports |
| [`RUNBOOK.md`](RUNBOOK.md) | On-call doc: splits, run commands, regression-check semantics, common failure modes, quarterly val rotation |

## Where to read next

- [`README.md`](README.md) -- architecture + scorecard + "what the agent is and isn't"
- [`CHANGELOG.md`](CHANGELOG.md) -- v0.1 to v0.9 lever-by-lever lift table
- [`sandbox/RESULTS_FRONTIER.md`](sandbox/RESULTS_FRONTIER.md) -- 11-row ablation across model + pipeline configurations
- [`RUNBOOK.md`](RUNBOOK.md) -- production ops
- [`sandbox/run_blinded.py`](sandbox/run_blinded.py) -- the harness; ~250 lines, designed to be read end-to-end

## Sister repos

- [`therapy-agent`](https://github.com/xX-its-amit-Xx/therapy-agent) -- the LangGraph pipeline. 9 nodes, 9 tools, 3 LLM backends (Anthropic / OpenAI / llama-cpp).
- [`fda-strategy-triples`](https://github.com/xX-its-amit-Xx/fda-strategy-triples) -- the v0.1.0 dataset shipped as a Python package.
- [`g2p-rag`](https://github.com/xX-its-amit-Xx/g2p-rag) -- the per-residue protein knowledge retriever (ChromaDB + BM25 hybrid). **Wired into therapy-agent as of 2026-05-31**: the local ChromaDB index covers all 47 benchmark genes (684 chunks across domain / variant_cluster / protein_summary types). The previous "UniProt fallback" path only fires now when the index is genuinely unavailable.
- [`g2p-agent`](https://github.com/xX-its-amit-Xx/g2p-agent) -- variant-interpretation sibling that depends on g2p-rag.
