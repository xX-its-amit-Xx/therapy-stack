# Round notes -- v0.10 (g2p-rag actually wired in)

A single-page summary of what shipped in this round. Read after
[ROUND_NOTES_v0.9.x.md](ROUND_NOTES_v0.9.x.md) for the v0.9.x context.

## The architectural lie this round fixes

The README architecture diagram has shown `g2p-rag` as a retrieval
component since v0.1. The bench has reported `source='g2p-rag …'` on
every case. But for the entire v0.2–v0.9.x arc the integration was
broken:

1. **Wrong import path in [therapy-agent/.../g2p_tool.py:35](https://github.com/xX-its-amit-Xx/therapy-agent/blob/main/src/therapy_agent/tools/g2p_tool.py#L35)** — `from g2p_rag import G2PRetrieverLangChain` would have ImportError'd because the class lives at `g2p_rag.integrations.langchain.G2PRetrieverLangChain`, not the top level.
2. **Wrong constructor signature** — `G2PRetrieverLangChain(k=K)` is missing the required `retriever=…` positional. The class wraps an existing `G2PRetriever`, not its config.
3. **Upstream G2P portal API was retired.** Even if therapy-agent's wiring were correct, the package's `/gene-transcript-protein-isoform-structure-map/{symbol}` and `/protein-features/{uniprot}` endpoints returned 404 by 2026-05. The current API is `/api/gene/{symbol}` returning metadata + cross-refs only.

Every "g2p-rag" string in result JSONs from v0.2 to v0.9.x was actually `[g2p-rag UniProt fallback]` — direct UniProt REST calls shaped to mimic g2p-rag's chunk format. No ChromaDB, no embedding-based ranking, no semantic search.

## What v0.10 ships

| Change | Commit |
|---|---|
| g2p-rag: adapt fetch.py to current G2P `/api/gene/{symbol}` endpoint + route per-residue features through UniProt direct | [`g2p-rag@a2e2d27`](https://github.com/xX-its-amit-Xx/g2p-rag/commit/a2e2d27) |
| g2p-rag: chunk.py pulls length / sequence / PPI from `features.*` instead of the now-empty `structure.*` fields | [`g2p-rag@e2778e3`](https://github.com/xX-its-amit-Xx/g2p-rag/commit/e2778e3) |
| therapy-agent: fix g2p_tool.py — correct import path, correct constructor, gene_filter per call, modern LangChain `.ainvoke` | [`therapy-agent@13093f0`](https://github.com/xX-its-amit-Xx/therapy-agent/commit/13093f0) |
| therapy-agent: config.get_g2p_index_dir() — resolves to sibling-repo `data/chroma` by default; `G2P_INDEX_DIR` env overrides | same |
| therapy-stack: README + SUMMARY + CHANGELOG say "g2p-rag actually wired in" — was misleading for the prior arc | [`therapy-stack@90d387d`](https://github.com/xX-its-amit-Xx/therapy-stack/commit/90d387d) |

## The ChromaDB index this round built

- **47 benchmark genes** ingested (covers every disease gene + every FDA target across dev / val / adversarial splits).
- **684 chunks** across the three chunk types: `domain`, `variant_cluster`, `protein_summary`.
- ChromaDB lives at `D:\Users\ashenoy00000\.windsurf\g2p-rag\data\chroma`. Override via `G2P_INDEX_DIR` for CI / alternate hosts.

## End-to-end smoke verification

5 benchmark genes, all return `source='g2p-rag (package)'` (was `'g2p-rag UniProt fallback'` before):

```
CYP21A2    src=g2p-rag (package)  n=5  all-gene-match=True
SERPING1   src=g2p-rag (package)  n=3  all-gene-match=True
PIGA       src=g2p-rag (package)  n=1  all-gene-match=True
BMPR2      src=g2p-rag (package)  n=5  all-gene-match=True
UMOD       src=g2p-rag (package)  n=5  all-gene-match=True
```

The UniProt fallback path now only fires when `g2p_rag` is genuinely unavailable (import error) or the index lookup itself fails. The documented contract finally matches the runtime behaviour.

## What's still TBD (v0.11+)

- **Full val pass with g2p-rag active.** Single-case smoke verified the path runs; impact on the headline number (does richer retrieval move Crinecerfont / Iptacopan / Sotatercept?) is one bench away.
- **Chunk-content depth.** The current chunks are mostly UniProt-summary + ClinVar variant lists. The G2P portal has richer per-residue data (PDB list, AlphaFold pLDDT, MaveDB scores) that the current ingest doesn't surface because it's not in the new `/api/gene/` endpoint either. Future versions of the portal API may restore this.
- **Stale-index detection.** If the curator adds a benchmark case for a gene not in the index, the agent silently falls back to UniProt and the result JSON doesn't flag the gap. A cheap fix is to check `coll.metadata` for index version + gene list at agent init.
- **Sandbox venv installability.** D: drive is at 99% — the sandbox venv can't fit `chromadb` + `sentence-transformers` directly. Verification used `g2p-rag/.venv` via `uv pip install -e --no-deps therapy-agent`. CI will need the deps in one place; that's a release-engineering task.

## Where to read next

- [ROUND_NOTES_v0.9.x.md](ROUND_NOTES_v0.9.x.md) — the previous round (strategy guards)
- [CHANGELOG.md](CHANGELOG.md) — the lever-by-lever lift table
- [`scripts/README.md`](scripts/README.md) — production tools (now 25)
- [`g2p-rag`](https://github.com/xX-its-amit-Xx/g2p-rag) — the retriever, with the upstream-API adapter live in main
