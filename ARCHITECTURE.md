# Architecture

This document explains how `therapy-stack` composes its four child repos into a working end-to-end pipeline. It is meant to be read after the README.

## Design goals

1. **Each component is independently citable, testable, and replaceable.** A team that only cares about the retriever should be able to depend on `g2p-rag` alone.
2. **The orchestration layer holds no domain logic.** This repo wires components together and renders results. Anything that could be unit-tested in isolation belongs in a child repo.
3. **Reproducibility is a first-class concern.** Every published result references a pinned version of every component and a pinned dataset snapshot.

## Component responsibilities

### `fda-strategy-triples` — the gold standard

The dataset repo. Each entry encodes an FDA-approved (or clinically validated) therapeutic strategy as a triple:

```
(disease_gene, mechanism_of_action, intervention_target)
```

For example, the Ekterly entry is roughly:

```yaml
case_id: hae-serping1
disease_gene: SERPING1
disease: Hereditary angioedema
mechanism: Loss of C1-INH leads to unregulated plasma kallikrein activity
intervention_target: KLKB1
intervention_modality: monoclonal antibody
approved_drug: garadacimab (Ekterly)
approval_year: 2025
citations: [...]
```

The repo ships a thin loader API (`load_cases()`) but no logic — it is essentially curated YAML.

### `g2p-rag` — retrieval

Given a gene symbol, `g2p-rag` returns a ranked set of pathway-level evidence snippets sourced from Reactome, KEGG, and OmniPath. It exposes a single `retrieve(gene, k=10)` call and ships its own embedding index so the orchestration layer never touches raw pathway data.

Critically, the retriever has no knowledge of FDA approvals. It is a pure biology retriever. This is what makes the end-to-end evaluation meaningful: the agent must reason from pathway evidence to an intervention target, not memorize approved drugs.

### `therapy-agent` — reasoning

The agent that produces hypotheses. Its contract:

```
Input:  disease_gene (str), pathway_context (list[Snippet])
Output: ranked list of TherapeuticStrategy {target, modality, rationale, confidence}
```

The current v0.1.0 implementation is a single-shot Claude Opus call with structured output. It deliberately does **not** see the gold-standard intervention — that would defeat the evaluation. v0.2.0 will introduce multi-step reasoning where the agent can issue follow-up retrieval calls.

### `bio-rag-eval` — judging

`bio-rag-eval` scores a list of agent hypotheses against a gold-standard triple. It does this two ways:

- **Deterministic:** does the predicted `intervention_target` symbol appear in the agent's top-k? What rank?
- **Semantic (LLM-as-judge):** does the agent's rationale describe the same mechanism as the gold standard? This catches cases where the agent proposes a synonym (e.g., "plasma kallikrein" vs. "KLKB1") or a related but valid pathway node.

The output is a scorecard HTML document (the one checked into `assets/scorecard_v0.1.0.html`).

## End-to-end flow

```
1. fda-strategy-triples.load_cases() yields N cases.
2. For each case:
   a. g2p_rag.retrieve(case.disease_gene) → pathway_context
   b. therapy_agent.propose(case.disease_gene, pathway_context) → hypotheses
   c. bio_rag_eval.score(hypotheses, case.gold_triple) → CaseScore
3. bio_rag_eval.render_scorecard(scores) → assets/scorecard_vX.Y.Z.html
```

The driver lives in `scripts/run_e2e.sh`, which is a thin shell wrapper around a Python entrypoint that imports the four packages. That entrypoint is **the only Python code in this repo**, and it does nothing but call the four public APIs in order.

## What lives here vs. what doesn't

| Concern | Lives in |
|---|---|
| Case curation | `fda-strategy-triples` |
| Pathway parsing & embedding | `g2p-rag` |
| Prompting & LLM calls | `therapy-agent` |
| Scoring logic, judge prompts, HTML rendering | `bio-rag-eval` |
| Pinning versions, wiring components, running demos, documentation | `therapy-stack` (this repo) |

If you find yourself wanting to write algorithm code in this repo, **stop and put it in the right child repo**. The rule of thumb: if a unit test would be meaningful for it, it belongs in a child repo.

## Reproducibility

Every published scorecard is pinned to:

- A `requirements.txt` snapshot listing exact versions of the four packages
- A `fda-strategy-triples` release tag (the case set as of that date)
- A `g2p-rag` release tag (the embedding index)
- A `therapy-agent` release tag (the model + prompt version)
- A model identifier in the agent (e.g. `claude-opus-4-7`)

`assets/scorecard_v0.1.0.html` was generated with the pinned versions in [requirements.txt](requirements.txt).

## Versioning

`therapy-stack` releases follow the cadence of the child repos. A new minor release of any child triggers a new patch release here. A breaking API change in a child triggers a minor release here, and the scorecard is regenerated.
