# therapy-stack

> An open-source stack for AI-driven therapeutic strategy hypothesis generation, with reproducible evaluation.

`therapy-stack` is the orchestration layer that composes four focused packages into a single end-to-end demo: given a disease gene with a known causal mechanism, it generates a ranked list of therapeutic strategy hypotheses and scores them against FDA-approved precedents.

Domain algorithms live in the four child repos. This repo holds the orchestration, the published docs, and a minimal end-to-end harness in [`sandbox/`](sandbox/) that runs the whole pipeline locally against real data with **no API keys required** — a free, open-source 3 B Llama model on CPU.

---

## Architecture

```mermaid
flowchart LR
    subgraph data[Gold Standard]
        FDA[fda-strategy-triples<br/><sub>curated FDA cases<br/>gene → mechanism → drug</sub>]
    end

    subgraph retrieval[Retrieval]
        G2P[g2p-rag<br/><sub>gene-to-pathway<br/>RAG index</sub>]
    end

    subgraph agent[Reasoning]
        TA[g2p-agent<br/><sub>LLM agent that<br/>proposes strategies</sub>]
    end

    subgraph eval[Evaluation]
        BRE[bio-rag-eval<br/><sub>judge + scorecard</sub>]
    end

    FDA -- cases --> TA
    G2P -- pathway context --> TA
    TA -- hypotheses --> BRE
    FDA -- gold labels --> BRE
    BRE -- scorecard --> Output[(scorecard.html)]
```

---

## Why four repos?

Each child repo solves one well-defined problem and is independently testable, citable, and installable. The split mirrors the natural boundaries of the system: a dataset (`fda-strategy-triples`), a retriever (`g2p-rag`), a reasoner (`g2p-agent`), and a judge (`bio-rag-eval`). Anyone can swap out a single component — a different retriever, a different judge model — without forking the whole stack. `therapy-stack` is the demo that proves the pieces fit together.

Child repos:

| Repo | What it does |
|---|---|
| [`fda-strategy-triples`](https://github.com/xX-its-amit-Xx/fda-strategy-triples) | Curated dataset of FDA-approved therapeutic strategies as (gene, mechanism, drug) triples — 10 cases, human-validated against ChEMBL/DrugBank/DailyMed |
| [`g2p-rag`](https://github.com/xX-its-amit-Xx/g2p-rag) | Hybrid dense+sparse retrieval over the Broad Institute G2P portal (UniProt + AlphaFold + ClinVar) |
| [`g2p-agent`](https://github.com/xX-its-amit-Xx/g2p-agent) | Claude tool-using agent that answers variant-level questions over the g2p-rag index |
| [`bio-rag-eval`](https://github.com/xX-its-amit-Xx/bio-rag-eval) | LLM-as-judge evaluation harness with deterministic + semantic scoring |

---

## Quickstart — run the real blinded benchmark locally

The runnable demo lives in [`sandbox/`](sandbox/). It drives the **real `therapy-agent` LangGraph pipeline** with a local Llama-3.2-3B model via `llama-cpp-python` — no API keys, no GPU required.

```powershell
git clone https://github.com/xX-its-amit-Xx/therapy-stack.git
cd therapy-stack/sandbox

# Python 3.11 venv (uv handles the install)
uv venv --python 3.11 .venv
$env:UV_CACHE_DIR = "C:/uv-cache"  # uv cache off the project drive

# Runtime deps from abetlen's prebuilt CPU wheels
uv pip install --python ./.venv/Scripts/python.exe `
    llama-cpp-python `
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
uv pip install --python ./.venv/Scripts/python.exe `
    langgraph langchain-core httpx typer rich pydantic pyyaml `
    tenacity python-dotenv huggingface_hub pandas pyarrow requests
uv pip install --python ./.venv/Scripts/python.exe `
    -e ../../fda-strategy-triples --no-deps `
    -e ../../therapy-agent --no-deps

# Download Llama 3.2 3B Instruct Q4_K_M (~1.9 GB)
./.venv/Scripts/python.exe -c "from huggingface_hub import hf_hub_download; `
    hf_hub_download( `
      repo_id='bartowski/Llama-3.2-3B-Instruct-GGUF', `
      filename='Llama-3.2-3B-Instruct-Q4_K_M.gguf', `
      local_dir='C:/llama-models')"

# Blinded run: 10 YAML benchmark cases through the real therapy-agent
$env:THERAPY_AGENT_LLM_BACKEND = "llama"
./.venv/Scripts/python.exe run_blinded.py --out blinded_results.json
```

To run the Claude path instead, set `ANTHROPIC_API_KEY` and `THERAPY_AGENT_LLM_BACKEND=anthropic`. The prompts and tooling are identical.

---

## Demos

| Path | Description |
|---|---|
| [`sandbox/run_e2e.py`](sandbox/run_e2e.py) | Working end-to-end on real FDA cases with a local Llama-3.2-3B model — no API key |
| [`sandbox/RESULTS.md`](sandbox/RESULTS.md) | Per-case agent traces and ranks from the most recent run |

---

## Latest scorecard — v0.7 (final ablation)

Six configurations on the same 16-dev / 6-val split. Inputs are `gene + mutation + disease_phenotype` only (no FDA drug or target names). Per-case detail in [`sandbox/RESULTS_FRONTIER.md`](sandbox/RESULTS_FRONTIER.md). The four pipeline improvements stacked since the prior round: (i) multi-target acceptance scoring against the FDA-validated set per disease; (ii) `find_signaling_family` tool for paralog/family discovery; (iii) Stage-2 bypass when the agentic research has proposed a non-disease-gene target (closes the "rationale says ACVR2B, target_protein writes BMPR2" failure); (iv) full-pipeline self-consistency (`--self-consistency 3`, majority vote on canonical HGNC target).

| Backend | Set | Target | Hard | Easy | Wall | Cost |
|---|---|---|---|---|---|---|
| R1-Distill 8B (no tools) | dev | 13/16 | 6/8 | 7/8 | 127 min | local |
| R1-Distill 8B (no tools) | val | 3/6 | 0/3 | 3/3 | 46 min | local |
| GPT-4o (no tools) | dev | 16/16 | 8/8 | 8/8 | 4 min | $0.06 |
| GPT-4o (no tools) | val | 2/6 | 0/3 | 2/3 | 1 min | $0.03 |
| GPT-4o + tool-use | dev | 15/16 | 7/8 | 8/8 | 6 min | $0.06 |
| GPT-4o + tool-use | val | 4/6 | 1/3 | 3/3 | 2 min | $0.03 |
| **GPT-4o + tool-use + multi-target + SC3** | **dev** | **15/16** | **7/8** | **8/8** | **11 min** | **$0.07** |
| **GPT-4o + tool-use + multi-target + SC3** | **val** | **4/6** | **1/3** | **3/3** | **4 min** | **$0.03** |

**Baselines (no LLM):** disease-gene 9/16 dev, 3/6 val (after stripping the SERPING1-as-HAE-valid-target leak). first-Reactome-interactor 5/16 dev, 1/6 val.

### What the latest improvements did and didn't move

- **Multi-target acceptance (`valid_targets` in YAMLs)** properly recognizes that SCD has voxelotor (HBB), Casgevy (BCL11A), hydroxyurea (HBG induction) and crizanlizumab (SELP) — any defensible. HAE has KLKB1, F12, BDKRB2. PNH has C5, CFB, C3. Vorasidenib hits IDH1+IDH2. The number didn't move because the existing recoveries were already on the primary target; the change adds rigor to the score rather than passing extra cases.
- **`find_signaling_family` tool** correctly surfaced the BMP/activin family (BMPR2 → ACVR2A, ACVR2B, INHBA, GDF8, GDF11) for Sotatercept. The agentic loop proposed ACVR2B. Strategy_synthesis Stage 2 still wrote BMPR2 into `target_protein` 3/3 times, even with the new deference prompt. The failure is field-vs-rationale alignment, not retrieval. Open question.
- **Stage-2 bypass when research proposes non-disease-gene target** fires when it triggers, but Sotatercept research's proposal was inconsistent across 3 self-consistency runs (research itself sometimes converged on BMPR2). So bypass didn't activate.
- **Full-pipeline self-consistency (SC3)** dampened run-to-run variance, but on N=6 val the noise was already statistical — voting didn't change the headline.

### The honest framing of v0.7

The agent reliably gets `(disease gene, mutation, phenotype) → defensible target` when:
- the target is the disease gene itself (8/8 dev easy, 3/3 val easy);
- the target is in the immediate Reactome / UniProt interactor neighborhood of the disease gene (7/8 dev hard);
- the agent can chain mechanism → pathway role → specific protein with up to 4 follow-up retrieval calls (Garadacimab F12 win, Resmetirom THRB win).

It does NOT reliably propose targets that require:
- 4+ hop hormonal-feedback reasoning (Crinecerfont, where the HPA axis is correctly identified but the specific receptor — CRHR1 vs MC2R vs NR3C1 — varies per run);
- recognition that a specific receptor-family member is a *ligand trap surface* (Sotatercept — research finds ACVR2B but the final answer reverts to the disease gene);
- the 4-hop chain `PIGA → GPI deficiency → CD55/CD59 loss → complement attack → block C5` (PNH).

A fair pitch: **a retrieval-augmented FDA-target *explainer* for known biology**, not a novel-target *discoverer*. Used as a suggestion / sanity-check surface alongside a domain expert, the system is useful.

---

## Cite this work

If you use `therapy-stack` or any of its components in your research, please cite the relevant child repo(s):

```bibtex
@software{shenoy_therapy_stack_2026,
  author  = {Shenoy, Amit},
  title   = {therapy-stack: An open-source orchestration layer for AI-driven therapeutic strategy generation},
  year    = {2026},
  url     = {https://github.com/xX-its-amit-Xx/therapy-stack},
  version = {0.1.0}
}

@software{shenoy_g2p_rag_2026,
  author  = {Shenoy, Amit},
  title   = {g2p-rag: Retrieval-augmented generation over the Broad Institute G2P portal},
  year    = {2026},
  url     = {https://github.com/xX-its-amit-Xx/g2p-rag},
  version = {0.1.0}
}

@software{shenoy_fda_strategy_triples_2026,
  author  = {Shenoy, Amit},
  title   = {fda-strategy-triples: A curated dataset of FDA-approved therapeutic strategies},
  year    = {2026},
  url     = {https://github.com/xX-its-amit-Xx/fda-strategy-triples},
  version = {0.1.0}
}

@software{shenoy_g2p_agent_2026,
  author  = {Shenoy, Amit},
  title   = {g2p-agent: A retrieval-augmented Claude agent over G2P portal data},
  year    = {2026},
  url     = {https://github.com/xX-its-amit-Xx/g2p-agent},
  version = {0.1.0}
}

@software{shenoy_bio_rag_eval_2026,
  author  = {Shenoy, Amit},
  title   = {bio-rag-eval: LLM-as-judge evaluation harness for biomedical RAG},
  year    = {2026},
  url     = {https://github.com/xX-its-amit-Xx/bio-rag-eval},
  version = {0.1.0}
}
```

---

## Roadmap

**v0.2.0 targets:**
- Expand the FDA case set from 10 → 30+ approvals, including more recent 2024–2025 entries
- Add a second LLM judge (GPT-4-class) to cross-check `bio-rag-eval` scores and report inter-judge agreement
- Expand pathway coverage in `g2p-rag` to include WikiPathways and a curated subset of SIGNOR
- Multi-step agent traces: let `therapy-agent` issue follow-up retrieval calls instead of one-shot reasoning
- A web UI for interactively browsing cases and scores, and the Claude-path scorecard side-by-side with the Llama-path scorecard

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deeper component-by-component explanation.

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
