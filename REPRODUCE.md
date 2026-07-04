# Reproducibility Manifest -- therapy-stack

## What this document is

This file is the single source of truth for reproducing any published number
in `therapy-stack`. Every headline result (e.g. "9/12 on val with R1-Distill
8B", "15/16 on dev with GPT-4o", "Crinecerfont CRHR1 recovered in v0.11") is
pinned to exact commits in four sibling repos, an exact ChromaDB SHA256, an
exact GGUF model SHA256, and an exact benchmark YAML count. The recipe below
takes a clean machine to a re-derivation of every published row in the
`CHANGELOG.md` lever table and the `README.md` scorecard. If a number cannot
be re-derived from the steps here, it is a reproducibility bug -- file an
issue against `therapy-stack` rather than re-running with newer pins.

## Quick-start reproducer (one command)

After cloning the four repos at the pinned commits (see "Environment pinning"
below) and downloading the GGUF model:

```bash
cd therapy-stack
make preflight    # pytest + lint + diversity + baselines (no LLM, ~1 min)
make bench-val    # 12-case val split, local Llama, ~99 min on 8-core CPU
```

The output `sandbox/val_results.json` should reproduce the headline numbers
in the `## Golden outputs` table. Compare with `scripts/run_diff.py` against
the reference run committed at `sandbox/blinded_v20_val_llama.json`.

## Environment pinning

### Repository commits (HEAD as of 2026-06-12)

| Repo | Commit | Role |
|---|---|---|
| [`therapy-stack`](https://github.com/xX-its-amit-Xx/therapy-stack) | `83b1134` | orchestration + harness + docs (this repo) |
| [`therapy-agent`](https://github.com/xX-its-amit-Xx/therapy-agent) | `9bbf41f` | LangGraph agent (Stage 1 pattern selector + Stage 2 target picker + tool-use) |
| [`g2p-rag`](https://github.com/xX-its-amit-Xx/g2p-rag) | `7484e15` | ChromaDB retrieval over G2P portal + UniProt + ClinVar |
| [`fda-strategy-triples`](https://github.com/xX-its-amit-Xx/fda-strategy-triples) | `84911e2` | curated FDA case dataset |

The `bio-rag-eval` repo (`ddcf6d5`) is referenced for the production scoring
path but is not exercised by the local-Llama benchmark; the harness in
`sandbox/run_blinded.py` does deterministic symbol-overlap scoring inline.

### Python dependencies

CI installs the pinned set from [`requirements-ci.txt`](requirements-ci.txt).
The complete list (every version is exact, no `>=`):

```
pyyaml==6.0.3
pandas==3.0.3
pyarrow==24.0.0
requests==2.34.2
httpx==0.28.1
tenacity==9.1.4
python-dotenv==1.2.2
langgraph==1.2.1
langchain-core==1.4.0
pydantic==2.13.4
typer==0.25.1
rich==15.0.0
pytest==9.0.3
anthropic==0.69.0
```

The two sibling repos are installed editable with `--no-deps` so this file is
the single source of truth for runtime package versions. `g2p-rag` uses
`uv.lock` (committed at `g2p-rag@7484e15`); regenerate the venv with
`uv sync`.

### Embedding model pin

The ChromaDB index was built with HuggingFace
`sentence-transformers/all-MiniLM-L6-v2`. The HuggingFace revision SHA is
captured at ingest time and written into each chunk's metadata; consumers
verify it via `g2p_rag.embed.SentenceTransformerEmbedder.model_revision`.
A mismatch between the consumer's loaded revision and the index's recorded
revision raises at retrieval time (see `g2p-rag@9496405` "wire
print_index_manifest into every cookbook").

### llama-cpp-python + GGUF SHA256s

`llama-cpp-python` is installed from abetlen's prebuilt CPU wheels:
`https://abetlen.github.io/llama-cpp-python/whl/cpu`. No specific pin is
required; the GGUF model is the load-bearing artifact.

| GGUF file | SHA256 | Size | Used by |
|---|---|---|---|
| `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | `6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff` | 2.0 GB | sandbox/run_e2e.py demo (v0.1) |
| `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | (8B baseline; SHA on request) | 4.9 GB | v0.6 baseline |
| `DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf` | `87bcba20b4846d8dadf753d3ff48f9285d131fc95e3e0e7e934d4f20bc896f5d` | 4.9 GB | v0.7 onwards (default; the val 9/12 number) |

All three files live under `C:/llama-models/` (Windows) or
`~/llama-models/` (Linux/macOS). Set `LLAMA_MODEL_PATH` to point at the
desired file.

### API model versions (cloud paths only)

| Provider | Model id | Used by |
|---|---|---|
| Anthropic | `claude-sonnet-4-6` | CI benchmark job (`.github/workflows/benchmark.yml` line 146/155) |
| Anthropic | `claude-opus-4-7` | production path (therapy-agent default) |
| OpenAI | `gpt-4o-2024-08-06` | v0.7+frontier dev scorecard, rationale_judge |
| OpenAI | `gpt-4o-mini-2024-07-18` | rationale_judge cheap mode |

Cloud paths are NOT required to reproduce the headline open-weights number
(9/12 val). They are required only to reproduce the v0.7+frontier row.

## Data pinning

### ChromaDB index

| Artifact | Value |
|---|---|
| Collection name | `g2p_proteins` |
| Persist directory | `g2p-rag/data/chroma/` |
| Chunk count | 948 |
| sqlite SHA256 | `50ec553884bd8ecc2feaefa00c3d0ca19d5127df68b699afb941a37f70712de2` |
| Gene coverage | 50 genes (the 47 benchmark genes + 3 cookbook genes) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Chunk types | `domain`, `variant_cluster`, `protein_summary`, `function`, `subunit`, `disease`, `pathway` |

The index is reproducible two ways:
1. **Download** (preferred): `cd g2p-rag && make download-index` -- pulls
   `chroma_index_v0.1.0.tar.gz` + `chroma_index_v0.1.0.sha256` from
   `g2p-rag/releases/v0.1.0`, verifies the tarball SHA, and untars into
   `data/chroma/`. Idempotent.
2. **Rebuild from snapshots**: `python sandbox/do_ingest.py` -- re-ingests
   from the pinned upstream snapshots (see next section) into a fresh
   ChromaDB. Slower (~30 min) but verifies the full ingest pipeline.

### Upstream data snapshots

The `g2p-rag/data/snapshots/` tree holds the raw UniProt / ClinVar / G2P-portal
fetches. Every gene directory has three JSONs (`uniprot.json`, `clinvar.json`,
`g2p.json`); every JSON is SHA256-pinned in
`g2p-rag/data/snapshots/.manifest.json`.

| Manifest artifact | Value |
|---|---|
| Path | `g2p-rag/data/snapshots/.manifest.json` |
| SHA256 | `e9b0a2abcb1cbd38b4e1aa626cebd1bb53e5c8b6f7f849673b7f3dcee5933359` |
| Gene count | 50 |
| Earliest fetch | 2026-06-01T17:30:23Z |

A reproducer that fetches *fresh* upstream data and the snapshot SHAs differ
indicates upstream (UniProt or G2P portal) drift; treat that as a
data-pinning failure and use the committed snapshot tarball instead.

### Benchmark YAMLs

| Split | Path (relative to `therapy-agent` repo root) | Count |
|---|---|---|
| dev | `benchmarks/*.yaml` + `benchmarks/cases/*.yaml` | 16 |
| val | `benchmarks/heldout_2024_2025/*.yaml` | 12 |
| adversarial | `benchmarks/adversarial/*.yaml` | 4 |

The dev + val + adv counts (16 + 12 + 4 = 32) are the active total. The README
mentions 7 adversarial cases planned; the active count is 4. The harness's
`load_cases()` (in `sandbox/run_blinded.py`) is the authoritative loader --
if its return-count differs from this table, the split has drifted.

The smoke job validates these counts on every PR:

```yaml
# .github/workflows/benchmark.yml (smoke job)
- name: Validate YAML benchmarks parse
  run: |
    for s in ('dev', 'val', 'adversarial', 'all'):
        cases = load_cases(s)
        assert all('input' in c and 'expected_outputs' in c for c in cases)
```

A val edit is blocked by `scripts/val_integrity_check.py` (smoke step
"Val-integrity check") -- this is the only structural defense against the
val-peek failure mode documented in RUNBOOK section 8.

## Step-by-step reproducer

Every step is a copy-pasteable command. Tested on Windows PowerShell + git
bash; Linux/macOS equivalents use forward slashes. The full reproducer is
~100 minutes wall-clock on an 8-core CPU box with 64 GB RAM.

### 1. Clone the four repos at the pinned commits

```bash
mkdir therapy-stack-repro && cd therapy-stack-repro

git clone https://github.com/xX-its-amit-Xx/therapy-stack.git
git -C therapy-stack checkout 83b1134

git clone https://github.com/xX-its-amit-Xx/therapy-agent.git
git -C therapy-agent checkout 9bbf41f

git clone https://github.com/xX-its-amit-Xx/g2p-rag.git
git -C g2p-rag checkout 7484e15

git clone https://github.com/xX-its-amit-Xx/fda-strategy-triples.git
git -C fda-strategy-triples checkout 84911e2
```

All four repos must be siblings of one another -- `therapy-stack`'s harness
walks `..` to find them (see `get_therapy_agent_root()` in
`sandbox/run_blinded.py`).

### 2. Create the Python 3.11 venv and install pins

```bash
cd therapy-stack/sandbox
uv venv --python 3.11 .venv

# Runtime deps from the pinned requirements
uv pip install --python ./.venv/Scripts/python.exe \
  -r ../requirements-ci.txt

# llama-cpp-python (CPU wheels, no specific version pin)
uv pip install --python ./.venv/Scripts/python.exe \
  llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# Editable sibling installs (no deps; pins come from requirements-ci.txt)
uv pip install --python ./.venv/Scripts/python.exe \
  -e ../../fda-strategy-triples --no-deps \
  -e ../../therapy-agent --no-deps \
  -e ../../g2p-rag --no-deps
```

### 3. Download the ChromaDB index (or ingest fresh)

```bash
# Preferred: signed download
cd ../../g2p-rag
make download-index

# Alternative: rebuild from snapshots
python -m g2p_rag.cli ingest --snapshots data/snapshots --persist data/chroma
```

Verify the chunk count:

```bash
python -c "import chromadb; c=chromadb.PersistentClient(path='data/chroma'); \
  print('chunks:', c.get_collection('g2p_proteins').count())"
# Expected: chunks: 948
```

### 4. Download the GGUF model

```bash
./.venv/Scripts/python.exe -c "from huggingface_hub import hf_hub_download; \
  hf_hub_download( \
    repo_id='bartowski/DeepSeek-R1-Distill-Llama-8B-GGUF', \
    filename='DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf', \
    local_dir='C:/llama-models')"

sha256sum C:/llama-models/DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf
# Expected: 87bcba20b4846d8dadf753d3ff48f9285d131fc95e3e0e7e934d4f20bc896f5d
```

A mismatched SHA is a hard fail -- HuggingFace re-quantizations can change
byte-for-byte. Pull from the dated release if `bartowski/...-GGUF` has
drifted.

### 5. Run the benchmark

```bash
cd ../therapy-stack
export THERAPY_AGENT_LLM_BACKEND=llama
export LLAMA_MODEL_PATH=C:/llama-models/DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf

make bench-val   # ~99 min, writes sandbox/val_results.json
```

For the smoke path (no LLM, ~1 min):

```bash
make preflight   # pytest + benchmark_lint + dataset_diversity + baselines
```

### 6. Run a cookbook (closes the retrieval loop)

```bash
cd ../g2p-rag
./.venv/Scripts/python.exe cookbook/cyp21a2_crhr1_upstream_target.py \
  > PROPOSALS.md
```

The cookbook writes a `PROPOSALS.md` with inline chunk citations of the form
`[chunk P08686:protein_summary:full: protein_summary CYP21A2 full]`. Every
citation refers to a real chunk in the index by design (the cookbook
citation helper refuses to emit a fake citation -- see
`g2p-rag/cookbook/_citation.py`).

### 7. Verify with audit_proposals.py (closes the trust loop)

```bash
cd ../therapy-stack
./sandbox/.venv/Scripts/python.exe scripts/audit_proposals.py \
  ../g2p-rag/PROPOSALS.md --strict
```

Expected: exit code 0, every citation marked `OK`. A `FAIL` means a citation
points at a chunk the index has never heard of (model-fabricated source); a
`WARN` (or `FAIL` under `--strict`) means a quoted span isn't a verbatim
substring of the cited chunk (paraphrase / embellishment). The auditor
never trusts the citation token alone -- it re-queries Chroma.

### 8. Compare against the golden output

```bash
./sandbox/.venv/Scripts/python.exe scripts/run_diff.py \
  --baseline sandbox/blinded_v20_val_llama.json \
  --candidate sandbox/val_results.json \
  --label "repro: golden -> rerun"
```

A clean reproducer prints `DIFF: 0 cases regressed`. Per-case
`target_recovered` should match field-for-field.

## Golden outputs

The reference run is committed at
[`sandbox/blinded_v20_val_llama.json`](sandbox/blinded_v20_val_llama.json).
Headline aggregate values that a faithful reproducer must hit:

| Field | Expected value | Tolerance |
|---|---|---|
| `n_cases` | 12 | exact |
| `target_recovered` | 9 | within 1 case (see RUNBOOK section 4) |
| `modality_recovered` | 8 | within 1 case |
| `baseline_disease_gene_recovered` | 8 | exact (deterministic baseline) |
| `baseline_first_interactor_recovered` | 1 | exact (deterministic baseline) |
| `total_seconds` | 5939.4 (~99 min) | within 25% (cost regression threshold) |
| `wilson_ci_target` | [0.4677, 0.9111] | exact (function of target_recovered) |

Per-case anchors (the cases the agent is *expected* to recover on val):

| `case_id` | gene | expected_target | predicted_target (golden) | recovered |
|---|---|---|---|---|
| `aprocitentan_htn` | EDN1 | EDNRA | EDN1 | true (via `valid_target` alias EDN1) |
| `capivasertib_breast` | PIK3CA | AKT1 | -- | (see file for full per-case) |

The `target_recovered` flag per case lives in
`sandbox/blinded_v20_val_llama.json` under `results[i].target_recovered`. The
file is the golden artifact; this table is a summary anchor for human
inspection.

Equivalent golden runs for other configurations:
- dev / R1-Distill 8B: `sandbox/blinded_v20_dev_llama.json` (12/16)
- adversarial / R1-Distill 8B: `sandbox/blinded_v20_adv_llama.json` (1/4)
- val / GPT-4o + tools + SC3: `sandbox/blinded_v17_val_sc3.json` (4/6)

## Audit trail

Every published claim is anchored to a commit + a chunk + (where applicable)
a `chunk_id` in the ChromaDB collection. Lookups go through
`scripts/audit_proposals.py` (verifies chunk existence at audit time) and
`cookbook/_citation.py` (refuses to emit a fake citation at write time). The
two together close the loop: writes can't manufacture sources, reads can't
trust an unverified one.

| Published claim | Anchor commit | Anchor artifact |
|---|---|---|
| v0.11 Crinecerfont CRHR1 recovery | `therapy-stack@11acee3` | `sandbox/_v11_crinecerfont.json` |
| v0.11 audit walkback (prompt-leakage) | `therapy-stack@1a402fa` | `ROUND_NOTES_v0.11.md` "v0.11 audit follow-up" |
| v0.10 g2p-rag wired in | `therapy-stack@90d387d`, `g2p-rag@a2e2d27` | `sandbox/_v10_crinecerfont_with_g2prag.json` |
| 9/12 val headline (R1-Distill 8B) | `therapy-stack@<v0.8>` | `sandbox/blinded_v20_val_llama.json` |
| 15/16 dev headline (GPT-4o) | `therapy-agent@<v0.7>` | `sandbox/blinded_v16_dev_gpt4o_tools.json`, `baselines.json` |
| Leakage strip 7/10 → 4/10 (v0.2→v0.3) | `therapy-agent@<v0.3>` | `sandbox/blinded_v3.json` |
| Baseline disease-gene 8/12 on val | (deterministic) | computed by `make baselines`; gold-anchored to `valid_targets` field in val YAMLs |

A reviewer auditing any row above should:
1. Check out the anchor commit.
2. Open the anchor artifact (a `blinded_*.json` per-case result file).
3. Recompute the aggregate from `results[*].target_recovered`.
4. (For citation-bearing claims) Run `scripts/audit_proposals.py` against
   the cited markdown.

## CI link

The reference green CI run for the smoke + benchmark jobs is the latest
push to `main` at `therapy-stack@83b1134` (HEAD as of this manifest's
date). The workflow definition is at
[`.github/workflows/benchmark.yml`](.github/workflows/benchmark.yml).

Smoke job (always runs, no API key required, ~5 min):
- pytest (unit tests for scoring + audit_proposals)
- `scripts/benchmark_lint.py` (every YAML has the required fields; no
  FDA drug / brand leakage into the input block)
- `scripts/docs_lint.py` (every script has a module docstring)
- `scripts/val_integrity_check.py` (no edits to held-out val cases)
- `scripts/preflight.py` (diversity + baselines)

Benchmark job (runs only when `ANTHROPIC_API_KEY` repository secret is set,
~30 min):
- `run_blinded.py --set dev` with `claude-sonnet-4-6`
- `run_blinded.py --set val` with `claude-sonnet-4-6`
- `scripts/regression_check.py` against `baselines.json` (fails if val
  drops by >1 case from the locked 4/6)
- `scripts/run_diff.py` posts a sticky PR comment with the per-case diff
- `scripts/calibration.py` writes the ECE + Brier report
- Uploads `dev_results.json` + `val_results.json` as 30-day artifacts

To audit a historical CI run, navigate to the workflow run page on GitHub
and download `benchmark-results-<commit-sha>` -- the per-case JSONs are
the canonical record.

## How to cite

```bibtex
@software{shenoy_therapy_stack_2026,
  author    = {Shenoy, Amit},
  title     = {therapy-stack: An open-source orchestration layer for
               AI-driven therapeutic strategy generation},
  year      = {2026},
  url       = {https://github.com/xX-its-amit-Xx/therapy-stack},
  version   = {0.1.0},
  commit    = {83b1134},
  note      = {Reproducibility manifest: REPRODUCE.md. Per-case golden
               outputs in sandbox/blinded_v20_val_llama.json
               (val, R1-Distill 8B Q4_K_M, 9/12).}
}
```

The four child repos are individually citable; see
[README.md](README.md#cite-this-work) for the full bibtex block.
