# therapy-stack

> An open-source stack for AI-driven therapeutic strategy hypothesis generation, with reproducible evaluation.

`therapy-stack` is the orchestration layer that composes four focused packages into a single end-to-end demo: given a disease gene with a known causal mechanism, it generates a ranked list of therapeutic strategy hypotheses and scores them against FDA-approved precedents.

This repo contains **no model logic** — only orchestration, docs, and demo assets. Every algorithm lives in one of the four child repos below.

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
        TA[therapy-agent<br/><sub>LLM agent that<br/>proposes strategies</sub>]
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

See [assets/architecture.png](assets/architecture.png) for a rendered version.

---

## Why four repos?

Each child repo solves one well-defined problem and is independently testable, citable, and installable. The split mirrors the natural boundaries of the system: a dataset (`fda-strategy-triples`), a retriever (`g2p-rag`), a reasoner (`therapy-agent`), and a judge (`bio-rag-eval`). Anyone can swap out a single component — a different retriever, a different judge model — without forking the whole stack. `therapy-stack` is the demo that proves the pieces fit together.

Child repos:

| Repo | What it does |
|---|---|
| [`fda-strategy-triples`](https://github.com/shenoy-am/fda-strategy-triples) | Curated dataset of FDA-approved therapeutic strategies as (gene, mechanism, drug) triples |
| [`g2p-rag`](https://github.com/shenoy-am/g2p-rag) | Gene-to-pathway retrieval-augmented index over Reactome, KEGG, and OmniPath |
| [`therapy-agent`](https://github.com/shenoy-am/therapy-agent) | LLM agent that proposes ranked therapeutic strategies given a gene and pathway context |
| [`bio-rag-eval`](https://github.com/shenoy-am/bio-rag-eval) | LLM-as-judge evaluation harness with deterministic + semantic scoring |

---

## Quickstart

```bash
git clone https://github.com/shenoy-am/therapy-stack.git && cd therapy-stack
bash scripts/install_all.sh
bash scripts/run_e2e.sh
open assets/scorecard_v0.1.0.html
```

Requires Python 3.11+, an `ANTHROPIC_API_KEY` in your environment, and ~2 GB of disk for the RAG index.

For a containerized run instead:

```bash
docker compose up
```

---

## Demos

| Notebook | Description |
|---|---|
| [`demos/01_ekterly_walkthrough.ipynb`](demos/01_ekterly_walkthrough.ipynb) | End-to-end walkthrough on the SERPING1 → KLKB1 case (hereditary angioedema, Ekterly) |
| [`demos/02_brd4780_walkthrough.ipynb`](demos/02_brd4780_walkthrough.ipynb) | UMOD/MUC1 → TMED9 case (autosomal dominant tubulointerstitial kidney disease, BRD4780) |
| [`demos/03_full_benchmark.ipynb`](demos/03_full_benchmark.ipynb) | Runs all FDA cases in the v0.1.0 set, regenerates the scorecard, renders results |

A 90-second terminal recording of `run_e2e.sh` lives at [assets/demo.gif](assets/demo.gif).

---

## Latest scorecard (v0.1.0)

Rendered from [assets/scorecard_v0.1.0.html](assets/scorecard_v0.1.0.html).

| Case | Gene | Approved drug | Strategy recovered | Top-k | Judge score |
|---|---|---|---|---|---|
| Hereditary angioedema | SERPING1 | Ekterly (garadacimab) | ✅ KLKB1 inhibition | 1 | 0.94 |
| ADTKD-MUC1 | MUC1 | BRD4780 (preclinical) | ✅ TMED9 modulation | 2 | 0.88 |
| Spinal muscular atrophy | SMN1 | Spinraza (nusinersen) | ✅ SMN2 splicing modulation | 1 | 0.96 |
| Transthyretin amyloidosis | TTR | Onpattro (patisiran) | ✅ TTR knockdown | 1 | 0.97 |
| Sickle cell disease | HBB | Casgevy (exa-cel) | ✅ BCL11A disruption | 1 | 0.91 |
| Familial hypercholesterolemia | LDLR | Leqvio (inclisiran) | ✅ PCSK9 knockdown | 1 | 0.95 |
| Duchenne muscular dystrophy | DMD | Elevidys | ✅ Microdystrophin replacement | 2 | 0.83 |
| Cystic fibrosis | CFTR | Trikafta | ✅ CFTR potentiation + correction | 1 | 0.92 |
| Acute hepatic porphyria | ALAS1 | Givlaari | ✅ ALAS1 knockdown | 1 | 0.93 |
| Hereditary ATTR (polyneuropathy) | TTR | Wainua (eplontersen) | ✅ TTR antisense | 1 | 0.94 |

**Overall:** 10/10 cases recovered, mean judge score **0.92**, mean rank **1.2**.

---

## Cite this work

If you use `therapy-stack` or any of its components in your research, please cite the relevant child repo(s):

```bibtex
@software{shenoy_therapy_stack_2026,
  author  = {Shenoy, Amit},
  title   = {therapy-stack: An open-source orchestration layer for AI-driven therapeutic strategy generation},
  year    = {2026},
  url     = {https://github.com/shenoy-am/therapy-stack},
  version = {0.1.0}
}

@software{shenoy_g2p_rag_2026,
  author  = {Shenoy, Amit},
  title   = {g2p-rag: Gene-to-pathway retrieval-augmented generation},
  year    = {2026},
  url     = {https://github.com/shenoy-am/g2p-rag},
  version = {0.1.0}
}

@software{shenoy_fda_strategy_triples_2026,
  author  = {Shenoy, Amit},
  title   = {fda-strategy-triples: A curated dataset of FDA-approved therapeutic strategies},
  year    = {2026},
  url     = {https://github.com/shenoy-am/fda-strategy-triples},
  version = {0.1.0}
}

@software{shenoy_therapy_agent_2026,
  author  = {Shenoy, Amit},
  title   = {therapy-agent: An LLM agent for therapeutic strategy hypothesis generation},
  year    = {2026},
  url     = {https://github.com/shenoy-am/therapy-agent},
  version = {0.1.0}
}

@software{shenoy_bio_rag_eval_2026,
  author  = {Shenoy, Amit},
  title   = {bio-rag-eval: LLM-as-judge evaluation harness for biomedical RAG},
  year    = {2026},
  url     = {https://github.com/shenoy-am/bio-rag-eval},
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
- A web UI (deployed via the included `docker-compose.yml`) for interactively browsing cases and scores

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deeper component-by-component explanation.

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
