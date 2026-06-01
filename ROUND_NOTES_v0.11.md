# Round notes -- v0.11 (chunk enrichment + first measured improvement)

A single-page summary of what shipped in this round. Read after
[ROUND_NOTES_v0.10.md](ROUND_NOTES_v0.10.md) for the v0.10 wiring context.

## Headline: Crinecerfont CRHR1 recovered

For the first time across the entire v0.9 -> v0.11 arc, the agent picked
**CRHR1** as the target for Crinecerfont -- matching the expected
`feedback_axis_receptor` pattern. v0.10 wired g2p-rag in for real, but
the Crinecerfont case still landed on `MC2R` (right axis, wrong node).
v0.11's chunk enrichment moves it onto the correct node.

```
predicted_target: CRHR1
pattern_id:       9
target_kind:      feedback_axis_receptor
recovered:        TRUE (matches expected CRHR1)
confidence:       0.75
```

### Trajectory across versions

| Version  | Predicted target | Notes |
|---|---|---|
| v0.9 baseline | CYP21A2          | disease-gene-default (the model just echoed the patient's CAH gene) |
| v0.9.2b       | NR3C1            | right family (nuclear receptor), wrong axis position |
| v0.9.4        | MC2R             | right axis (HPA), wrong node (one step downstream of where Crinecerfont acts) |
| **v0.11**     | **CRHR1**        | **right axis, right node, right mechanism** |

## What v0.11 changed structurally

g2p-rag v0.1.1 broadens the ingest beyond protein-summary / domain /
variant-cluster into four new UniProt-derived chunk types:

- `FUNCTION`   -- the UniProt FUNCTION block (molecular role, ligands, downstream signalling)
- `PATHWAY`    -- explicit pathway membership (KEGG / Reactome cross-refs surfaced as text)
- `SUBUNIT`    -- complex composition, binding partners
- `DISEASE`    -- OMIM / MIM-curated disease associations and their mechanism notes

Index size went from **684 chunks -> 819 chunks** (+135 new biology
chunks across the 47 benchmark genes). The CRHR1 disease and function
chunks in particular carry the HPA-axis / ACTH-feedback language that
v0.10's protein-summary chunks didn't surface.

## Evidence the new chunks are actually being used

Rationale excerpt from the v0.11 result JSON:

> CRHR1 is the upstream receptor in the hypothalamic-pituitary-adrenal
> (HPA) axis that senses and responds to ACTH levels. It plays a key
> role in the feedback loop by driving the compensatory mechanisms,
> aligning with the feedback_axis_receptor pattern.

Two things to notice:

1. The phrase "upstream receptor in the hypothalamic-pituitary-adrenal
   (HPA) axis" is verbatim FUNCTION-chunk territory -- it isn't in the
   v0.10 protein-summary text for CRHR1.
2. The reasoning trace logs `g2p-rag: retrieved 5 chunk(s) via g2p-rag
   (package)` in v0.11, versus `g2p-rag: retrieved 3 chunk(s) via
   g2p-rag UniProt fallback` in v0.9.4. More chunks **and** chunks
   coming from the real package path, not the fallback.

The disambiguation story: at v0.9.4 the agent had MC2R domain +
variant-cluster text in front of it, which is enough to land on "ACTH
receptor" but not enough to back up the chain to the receptor that
**senses ACTH and closes the feedback loop**. The new DISEASE/FUNCTION
chunks for CRHR1 explicitly name that role, and the picker walks one
step further up the axis.

## What's still TBD (v0.12+)

- **Full val pass.** This is still one measured case. The val split has
  ~10 cases; the headline number can't move on n=1. Need a full bench
  run with the v0.1.1 index to see whether other cases benefit, stay
  flat, or regress.
- **Adversarial set.** v0.11's chunk-content win was on a case where
  the answer is recoverable from public UniProt text. The adversarial
  cases (where the correct target is **not** the most-described
  partner of the disease gene) will stress-test whether richer chunks
  also create new failure modes -- e.g. confidently retrieving the
  wrong partner because it now has a PATHWAY chunk too.
- **Possible regression on cases that didn't need the extra chunks.**
  Adding 135 chunks doubles the retrieval surface area. Cases that
  were already correct at v0.10 with 3-5 protein-summary chunks could
  in principle now retrieve a noisier mix and lose. Need the full val
  + dev sweep to rule that out.
- **Pinning the index version in result JSONs.** Right now the result
  JSON says `source='g2p-rag (package)'` but doesn't record which index
  build was active. Next round should stamp `index_version` alongside
  `chunk_count` so we can attribute lifts to specific ingest changes.

## Where to read next

- [ROUND_NOTES_v0.10.md](ROUND_NOTES_v0.10.md) -- the wiring round
- [ROUND_NOTES_v0.9.x.md](ROUND_NOTES_v0.9.x.md) -- the strategy-guard round
- [CHANGELOG.md](CHANGELOG.md) -- the lever-by-lever lift table
- [`g2p-rag`](https://github.com/xX-its-amit-Xx/g2p-rag) -- v0.1.1 ingest with FUNCTION/PATHWAY/SUBUNIT/DISEASE chunk types
- [`sandbox/_v94_crinecerfont.json`](sandbox/_v94_crinecerfont.json) -- v0.9.4 MC2R result for comparison
