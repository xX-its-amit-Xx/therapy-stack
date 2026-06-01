# Round notes -- v0.11 (chunk enrichment + partly-measured improvement)

A single-page summary of what shipped in this round. Read after
[ROUND_NOTES_v0.10.md](ROUND_NOTES_v0.10.md) for the v0.10 wiring context.

> **Audit follow-up (2026-06-01).** The v0.11 CRHR1 recovery is partly a
> prompt-leakage artifact, not a clean g2p-rag retrieval win. See the
> "v0.11 audit follow-up" section at the bottom of this file before
> citing the headline. The "first measurable g2p-rag improvement"
> framing has been walked back to "partly measurable, partly
> prompt-injected".

## Headline: Crinecerfont CRHR1 recovered (with caveat — see audit follow-up)

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

## v0.11 audit follow-up (2026-06-01)

A post-hoc audit of the v0.11 Crinecerfont CRHR1 recovery found that the
result is **partly attributable to prompt-level hints, not purely
g2p-rag retrieval**. The "first measurable g2p-rag improvement"
headline was over-claimed and is walked back here.

### What the audit found

Both prompts in `therapy-agent/src/therapy_agent/nodes/strategy_synthesis.py`
explicitly name CRHR1 as the correct answer for the CYP21A2 +
ACTH-driven CAH archetype:

- **Stage-1 system prompt (`_PATTERN_SELECTOR_SYSTEM`), line 82** -- the
  pattern-9 description itself names the case verbatim:
  > "Example archetypes: CAH (CYP21A2 LOF -> ACTH excess -> adrenal
  > androgen excess; block CRHR1), pituitary feedback loops in general."
- **Stage-1 NEGATIVE EXAMPLES block, line 92** -- the negative-example
  list literally describes the Crinecerfont test case and gives the
  answer:
  > "Disease gene CYP21A2 + ACTH-driven androgen excess phenotype:
  > chaperone is WRONG; pattern 9 (feedback-axis blockade, target
  > CRHR1) is right."
- **Stage-2 system prompt (`_TARGET_PICKER_SYSTEM`), line 141** -- the
  feedback_axis_receptor rule names CRHR1 / CRHR2 by symbol as the
  upstream HPA receptor to pick:
  > "...the RELEASING HORMONE receptor (e.g. CRHR1 / CRHR2 for the HPA
  > axis when ACTH is the toxic intermediate...)"

The test case under evaluation is Crinecerfont (CAH, CYP21A2 LOF,
ACTH-driven phenotype, expected target CRHR1). It is a *perfect
substring match* for the negative example on line 92.

### Why this is leakage, not "guard reasoning"

Crucially, the candidate list shown to the Stage-2 picker is the
g2p-rag interactor neighborhood of CYP21A2. Reactome / UniProt do not
return CRHR1 as a pathway interactor of CYP21A2 -- the two genes are
on opposite ends of the HPA axis, separated by the pituitary. So
**CRHR1 is not in the candidate set the picker is "choosing from"**.
The model is naming CRHR1 because the prompt told it to, not because
g2p-rag retrieved it.

The v0.11 chunk enrichment (FUNCTION / SUBUNIT / DISEASE / PATHWAY
chunks for the 47 benchmark genes) is real and the rationale text the
agent produces *is* enriched with HPA-axis language that maps to those
chunks -- but the **choice of target symbol** is driven by the prompt
hint, not by the new chunks.

### Walked-back claims

- "First measurable g2p-rag improvement" -> **"partly measurable,
  partly prompt-injected"**. The chunk count and rationale-text
  enrichment are real; the headline target-recovery on Crinecerfont
  cannot be attributed to g2p-rag alone.
- "v0.11's chunk enrichment moves it onto the correct node" -> the
  prompts moved it onto the correct node; the chunks supplied the
  surrounding rationale phrasing.
- The headline trajectory `CYP21A2 -> NR3C1 -> MC2R -> CRHR1` is real
  in terms of what the agent output across versions, but the v0.11 ->
  CRHR1 transition coincides with the v0.9.4 prompt rule on line 141
  having been written specifically for this archetype. The
  contribution of g2p-rag retrieval, the v0.9.x guards, and the prompt
  hint cannot be separated without a held-out CAH-archetype case that
  is *not* named in the prompts.

### What this means for next round

- The "g2p-rag enrichment is the lever that moved this case" claim
  needs an unambiguous test: a feedback-axis case whose specific
  answer is **not** in `_PATTERN_SELECTOR_SYSTEM` or
  `_TARGET_PICKER_SYSTEM`.
- The prompt examples should be sanitized for any benchmark case that
  is in dev / val / adversarial. The pattern-9 description can name
  the archetype mechanism without naming CRHR1 by symbol.
- The honest current claim is: g2p-rag v0.1.1 chunks add biology the
  v0.10 index didn't carry, and the rationale text now references that
  biology. Whether the chunks move target-recovery accuracy is still
  TBD on cases without prompt leakage.
