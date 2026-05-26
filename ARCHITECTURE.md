# Architecture

This document explains how `therapy-stack` composes its four child repos into a working end-to-end pipeline. It is meant to be read after the README.

## Design goals

1. **Each component is independently citable, testable, and replaceable.** A team that only cares about the retriever should be able to depend on `g2p-rag` alone.
2. **The orchestration layer holds no domain logic.** This repo wires components together and renders results. Anything that could be unit-tested in isolation belongs in a child repo.
3. **Reproducibility is a first-class concern.** Every published result references a pinned version of every component and a pinned dataset snapshot.

## Component responsibilities

### `fda-strategy-triples` — the gold standard

The dataset repo. Each entry encodes a real FDA-approved therapeutic strategy with provenance fields (PMID citation, DailyMed label URL, ChEMBL/DrugBank cross-validation flags). v0.1.0 ships 10 human-reviewed cases.

Example record (Leqvio / inclisiran):

```yaml
id: 3f1a2b4c-0010-...
drug_name_brand: Leqvio
drug_name_generic: inclisiran
indicated_disease: Heterozygous familial hypercholesterolemia (HeFH)...
associated_genes: [PCSK9, LDLR]
molecular_target: P53779 (PCSK9) - proprotein convertase subtilisin/kexin
                  type 9 mRNA (hepatic)
mechanism_class: siRNA
primary_citation_pmid: 31995867
chembl_validated: true
drugbank_validated: true
validated: true
reviewer: shenoy.am@husky.neu.edu
```

The repo ships a `load_dataset()` function returning a pandas DataFrame (or pydantic models with full provenance). No logic — curated, validated data.

### `g2p-rag` — retrieval

Given a gene symbol, `g2p-rag` returns a ranked set of protein-level evidence chunks (domain, variant-cluster, protein-summary) from the Broad Institute G2P portal, indexed with hybrid dense+sparse retrieval over a local ChromaDB. It exposes a `G2PRetriever.retrieve(query, k=10)` call.

For machines without a built G2P index, the [`sandbox/`](sandbox/) harness substitutes a UniProt REST retriever that returns the same kind of biology (FUNCTION, PATHWAY, SUBUNIT, PTM, DISEASE, LIPIDATION fields) — what g2p-rag is ultimately built on top of, minus the embedding layer.

Critically, the retriever has no knowledge of FDA approvals. The agent must reason from pathway/PTM/interaction evidence to an intervention target, not memorize approved drugs.

### `g2p-agent` — reasoning

The agent that produces hypotheses. Its contract:

```
Input:  disease_gene (str), retrieved_context (list[chunk])
Output: ranked list of TherapeuticStrategy {target, modality, rationale, confidence}
```

`g2p-agent` ships with two backends: an `AnthropicLLM` that drives Claude with tool-use, and a deterministic `MockLLM` for offline reproducibility. The [`sandbox/agent.py`](sandbox/agent.py) demo adds a third path: a local Llama-3.2-3B model via `llama-cpp-python` (CPU, no API key). All three obey the same contract — the orchestration layer doesn't change.

The agent deliberately does **not** see the gold-standard intervention. v0.2.0 will introduce multi-step reasoning where the agent issues follow-up retrieval calls.

### `bio-rag-eval` — judging

`bio-rag-eval` scores a list of agent hypotheses against a gold-standard triple. It does this two ways:

- **Deterministic:** does the predicted `intervention_target` symbol appear in the agent's top-k? What rank?
- **Semantic (LLM-as-judge):** does the agent's rationale describe the same mechanism as the gold standard? This catches cases where the agent proposes a synonym (e.g., "5-aminolevulinic acid synthase 1" vs. "ALAS1") or a related but valid pathway node.

The output is a structured scorecard — JSON + markdown rendered into the README's results table, plus the per-case traces in [`sandbox/RESULTS.md`](sandbox/RESULTS.md).

## End-to-end flow

```
1. fda_strategy_triples.load_dataset() yields N validated cases.
2. For each case:
   a. retriever.retrieve(case.disease_gene) → biology_context
      (G2PRetriever in production; UniProt REST in sandbox/)
   b. agent.propose(case.disease_gene, biology_context) → hypotheses
      (g2p-agent + Claude in production; Llama 3.2 3B in sandbox/)
   c. judge.score(hypotheses, case.molecular_target) → CaseScore
      (bio-rag-eval in production; deterministic symbol overlap in sandbox/)
3. Aggregate -> scorecard HTML / markdown.
```

There are two driver paths:

| Path | Driver | Model | Status |
|---|---|---|---|
| Sandbox (real, local, no key) | [`sandbox/run_e2e.py`](sandbox/run_e2e.py) | Llama-3.2-3B-Instruct via llama-cpp-python | **Working; 8/10 recovered** |
| Claude / production | direct use of `g2p-agent` + `bio-rag-eval` against a built `g2p-rag` index | claude-opus-4-7 via Anthropic SDK | Requires `ANTHROPIC_API_KEY` + a `g2p-rag` ingest |

## What lives here vs. what doesn't

| Concern | Lives in |
|---|---|
| Case curation, dataset validation | `fda-strategy-triples` |
| G2P portal ingestion, embedding, retrieval | `g2p-rag` |
| Claude tool-using agent loop, prompts | `g2p-agent` |
| Scoring metrics, judge prompts, HTML rendering | `bio-rag-eval` |
| Pinning versions, wiring components, running demos, documentation | `therapy-stack` (this repo) |
| Minimal local-only stand-ins (UniProt retriever, Llama agent, deterministic judge) for environments without API keys / G2P index | `therapy-stack/sandbox/` |

If you find yourself wanting to write algorithm code in the top-level of this repo, **stop and put it in the right child repo**. The sandbox is the one allowed exception — and only because the production components require infrastructure (API keys, embedding indexes) that not every developer has.

## Reproducibility

Every published scorecard is pinned to:

- A `requirements.txt` snapshot listing exact versions of the four packages
- A `fda-strategy-triples` release tag (the case set as of that date)
- A `g2p-rag` release tag (the embedding index)
- A `g2p-agent` release tag (the model + prompt version)
- A model identifier in the agent (e.g. `claude-opus-4-7` for production, `Llama-3.2-3B-Instruct-Q4_K_M` for the sandbox)

The current real result (2026-05-26) is in [`sandbox/RESULTS.md`](sandbox/RESULTS.md).

## Versioning

`therapy-stack` releases follow the cadence of the child repos. A new minor release of any child triggers a new patch release here. A breaking API change in a child triggers a minor release here, and the scorecard is regenerated.
