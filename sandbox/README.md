# sandbox/ — local end-to-end harness

This directory is the **runnable** end-to-end demo. It exists because the
four child packages (`g2p-rag`, `g2p-agent`, `fda-strategy-triples`,
`bio-rag-eval`) each carry their own heavy dependencies — Anthropic API
keys, ChromaDB indexes, OpenAI clients — that we can't assume are
present on every machine. The sandbox stands in with minimal,
no-API-key components that exercise the same orchestration shape.

| Stage | Stand-in here | Production component |
|---|---|---|
| Dataset | `fda_strategy_triples.load_dataset()` (real, installed) | same |
| Retrieval | `retriever.py` — UniProt REST | `g2p-rag` (Reactome + KEGG via ChromaDB) |
| Agent | `agent.py` — Llama-3.2-3B via `llama-cpp-python` | `g2p-agent` (Claude via Anthropic SDK) |
| Judge | `judge.py` — deterministic HGNC-symbol overlap | `bio-rag-eval` (LLM-as-judge + metrics) |

## How to reproduce

```powershell
cd sandbox
uv venv --python 3.11 .venv

# Install runtime deps; llama-cpp-python via abetlen's prebuilt CPU wheels.
$env:UV_CACHE_DIR = "C:/uv-cache"
uv pip install --python ./.venv/Scripts/python.exe `
    llama-cpp-python `
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
uv pip install --python ./.venv/Scripts/python.exe `
    huggingface_hub pandas pyarrow requests
uv pip install --python ./.venv/Scripts/python.exe `
    -e ../../fda-strategy-triples --no-deps

# Download Llama 3.2 3B Q4_K_M (~1.9 GB).
./.venv/Scripts/python.exe -c "from huggingface_hub import hf_hub_download; `
    hf_hub_download( `
      repo_id='bartowski/Llama-3.2-3B-Instruct-GGUF', `
      filename='Llama-3.2-3B-Instruct-Q4_K_M.gguf', `
      local_dir='C:/llama-models')"

# Run.
./.venv/Scripts/python.exe run_e2e.py --cases 10 --out results_all.json
```

End-to-end runtime on an 8-core Xeon (no GPU) is about 3 minutes for 10
cases — most of that is model decode time.

## What it measures

For each FDA approval in `fda-strategy-triples`:
1. Retrieve UniProt FUNCTION / PATHWAY / SUBUNIT / PTM / DISEASE /
   LIPIDATION fields for each associated gene.
2. Ask Llama-3.2-3B-Instruct to propose up to three ranked therapeutic
   strategies, given only the disease name + gene + retrieved context.
   The agent **never** sees the gold drug target.
3. Score by checking whether the gold target's HGNC symbol appears in
   any of the proposed strategies, with the rank of the matching one.

The agent's system prompt encodes five categorical reasoning moves
(loss-of-function vs toxic-gain, upstream-enzyme knockdown, PTM-enzyme
blockade, repressor disruption, regulator blockade) — but does not name
any of the specific genes that appear in the test set. See
[`agent.py`](agent.py).

## Headline result

| Metric | Value |
|---|---|
| Recovered (gold target in top-3) | **8 / 10** |
| Mean rank of correct target | **1.625** |
| Top-1 hits | **4 / 10** |
| Wall time per case (CPU) | ~22 s |
| Model | Llama-3.2-3B-Instruct, Q4_K_M (1.93 GB on disk) |

Per-case results in [`RESULTS.md`](RESULTS.md).

## What the failures tell us

Two cases missed — both informative:

- **Zokinvy (LMNA → FNTB).** The PTM field for LMNA *literally names*
  FNTA/FNTB as the farnesyltransferase. The 3B model still fails to
  chain "progerin's CAAX motif is farnesylated → that farnesyl traps it
  at the membrane → block the transferase to prevent the trapping" and
  defaults to "fix the nuclear envelope". A bigger model or a more
  explicit chain-of-thought scaffold would likely close this.
- **Amvuttra (TTR → TTR mRNA).** The model over-reasons. It proposes
  blocking glycosylation (STT3B) or RBP4 binding instead of just
  knocking down the toxic transthyretin. Sometimes "the disease gene IS
  the target" is the right answer; the system prompt biases too hard
  against that.

## Files

- [`retriever.py`](retriever.py) — UniProt REST client
- [`agent.py`](agent.py) — Llama prompt + JSON parser
- [`judge.py`](judge.py) — deterministic target-overlap scorer
- [`run_e2e.py`](run_e2e.py) — driver
- [`results_all.json`](results_all.json) — last full run, raw outputs
- [`RESULTS.md`](RESULTS.md) — per-case summary
