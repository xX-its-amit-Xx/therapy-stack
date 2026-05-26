# sandbox/ — local end-to-end harness

This directory drives the **real `therapy-agent` LangGraph pipeline** end-to-end with a local Llama-3.2-3B model, against the 10 blinded YAML benchmark cases that ship in `therapy-agent/benchmarks/`. No API keys, no GPU.

## What composes what

| Stage | Production component | What runs here |
|---|---|---|
| Dataset | `fda-strategy-triples` (installed, real loader) | same |
| Variant lookup | `g2p-rag` ChromaDB + ClinVar | ClinVar (live) + HTTP fallback when no g2p-rag index |
| Pathway expansion | Reactome ContentService (live) | same |
| Druggable target search | ChEMBL + DrugBank (live) | same |
| Strategy synthesis | `therapy-agent` (LangGraph) → Claude | `therapy-agent` (same code) → local Llama-3.2-3B via a new pluggable LLM backend in `therapy_agent.llm` |
| Self-critique | `therapy-agent` (LangGraph) → Claude | same → local Llama-3.2-3B |
| Judging | `bio-rag-eval` | inline deterministic check in [`run_blinded.py`](run_blinded.py) |

The LLM backend lives in [`therapy-agent/src/therapy_agent/llm.py`](../../therapy-agent/src/therapy_agent/llm.py); selection is via env var `THERAPY_AGENT_LLM_BACKEND=anthropic|llama`.

## How to reproduce

```powershell
cd sandbox
uv venv --python 3.11 .venv

$env:UV_CACHE_DIR = "C:/uv-cache"
uv pip install --python ./.venv/Scripts/python.exe `
    llama-cpp-python `
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
uv pip install --python ./.venv/Scripts/python.exe `
    langgraph langchain-core httpx typer rich pydantic pyyaml `
    tenacity python-dotenv huggingface_hub pandas pyarrow requests

uv pip install --python ./.venv/Scripts/python.exe `
    -e ../../fda-strategy-triples --no-deps `
    -e ../../therapy-agent --no-deps

./.venv/Scripts/python.exe -c "from huggingface_hub import hf_hub_download; `
    hf_hub_download( `
      repo_id='bartowski/Llama-3.2-3B-Instruct-GGUF', `
      filename='Llama-3.2-3B-Instruct-Q4_K_M.gguf', `
      local_dir='C:/llama-models')"

$env:THERAPY_AGENT_LLM_BACKEND = "llama"
./.venv/Scripts/python.exe run_blinded.py --out blinded_results.json
```

Wall time: ~14 min for 10 cases on an 8-core CPU.

## What the harness measures

Each YAML case has the input fields `gene`, `mutation`, `disease_phenotype`. The expected `target_protein` (and the FDA drug names) are **only** in the `expected_outputs` block — the agent never sees them. The harness:

1. Calls `therapy_agent.graph.run_agent(gene, mutation, disease_phenotype)`.
2. Pulls the `target_protein` field out of the agent's final `strategy` state.
3. Substring-matches it against the expected target or any declared alias.

## Headline result

**7 / 10 blinded recovery** with `THERAPY_AGENT_LLM_BACKEND=llama` (Llama-3.2-3B-Instruct Q4_K_M). Per-case traces in [`RESULTS_BLINDED.md`](RESULTS_BLINDED.md).

## Leakage discipline

I removed the following from the `therapy-agent` package before the v0.2 run, because each was test-case leakage:

- **Two verbatim worked examples** in `strategy_synthesis.py`'s system prompt: a complete SERPING1→KLKB1 strategy object and a complete UMOD→TMED9 strategy object, both naming approved drugs by brand name. The system prompt now uses only categorical patterns (no test-set gene names).
- **A few-shot example block** in `mechanism_classifier.py` that named SERPING1, UMOD, MUC1, HBB, and DMD with their mechanism classes. Replaced with a generic schema + heuristic list.
- **Hardcoded narrative `pathway_context` strings** in `reactome_query.py`'s `GENE_PATHWAY_FALLBACK` that literally named the FDA-approved drug for each disease (e.g. *"Givosiran silences ALAS1 mRNA via siRNA"*, *"Migalastat (pharmacological chaperone) stabilizes amenable GLA variants"*). Replaced with neutral one-liners describing only the disease gene's pathway role.

What remained is real biology that any live Reactome / IntAct / UniProt query would also return — pathway memberships and interactor lists. The agent still has to *reason* from these to a target.

## What failed and why

Three cases miss consistently across four prompt-iteration rounds:

- **`als_sod1`** (expected: SOD1 mRNA knockdown). Mechanism classifies as dominant_negative. Pattern 5 in the system prompt says "knock down the disease gene's mRNA" for toxic-gain proteins. The 3 B model still picks PRDX1, a downstream antioxidant. The rationale describes the right mechanism; the `target_protein` field doesn't follow.
- **`dmd_exon51`** (expected: DMD exon-skipping ASO). The mutation is an out-of-frame exon 48-50 deletion. Pattern 7 explicitly handles this (target an adjacent exon of the same gene). The model picks SGCA (sarcoglycan in the same complex) instead.
- **`scd_hbb`** (expected: HBB stabilizer or BCL11A enhancer). Gain-of-function polymer. The model walks two regulatory hops to MYB (a TF regulating BCL11A) instead of either HBB or BCL11A.

All three failures involve cases where the right target is *the disease gene itself*, and the 3 B model over-reaches to a downstream partner despite the prompt's symmetric triage. With `THERAPY_AGENT_LLM_BACKEND=anthropic` (the default Claude path), these should close — the pipeline and prompts are identical, only the LLM swaps.

## Files

- [`run_blinded.py`](run_blinded.py) — driver: loads YAML cases, calls `run_agent`, scores
- [`RESULTS_BLINDED.md`](RESULTS_BLINDED.md) — per-case rationales + summary table
- [`blinded_v5.json`](blinded_v5.json) (gitignored) — raw last-run JSON
- [`retriever.py`, `agent.py`, `judge.py`, `run_e2e.py`](.) — earlier v0.1 standalone harness (uses UniProt + Llama directly, no `therapy-agent` package). Kept as a no-package fallback path.
- [`RESULTS.md`](RESULTS.md) — v0.1 standalone-harness results, **not** blinded
