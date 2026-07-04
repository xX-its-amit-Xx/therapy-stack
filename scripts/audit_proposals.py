"""Audit citations in a PROPOSALS.md file against the g2p-rag ChromaDB index.

Contract
--------
PROPOSALS.md is a human-readable list of therapy/target proposals. Every
factual claim is expected to carry an inline chunk citation of the form::

    [chunk <UNIPROT>:<chunk_type>:<start>-<end>: <chunk_type> <GENE> <start>-<end>]

(or with ``full`` / ``-`` standing in for the residue range on protein-level
chunks). The cookbook citation helper enforces this format at *write* time --
it refuses to emit a citation unless the chunk really exists in the index.

This script enforces the same discipline at *audit* time, on a finished
PROPOSALS.md document, against the live Chroma collection. Specifically:

  1. Every cited chunk must EXIST in the index (matched on
     uniprot_id + chunk_type + residue_start + residue_end). A citation that
     points to a chunk the index has never heard of is a FAIL -- the proposal
     is making up sources.

  2. Any double-quoted span found near a citation (within ~3 lines before it)
     must appear as a verbatim substring of the cited chunk's document text.
     A near-quote that is not a real substring is a WARN (paraphrase /
     embellishment) under default mode, or a FAIL under ``--strict``.

The script never trusts the citation token alone -- it always re-queries
Chroma. This is the only way to catch model-fabricated citations that look
syntactically correct.

Exit codes
----------
  0 -- every citation resolves and (in strict mode) every quote matches.
  1 -- at least one FAIL was emitted; CI should block on this.

CLI
---
    python scripts/audit_proposals.py <proposals.md> [--chroma-path PATH] [--strict]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import chromadb

COLLECTION = "g2p_proteins"

# Citation token. Tolerates both halves of the prefix:protein_summary:1-766
# form *and* protein-level chunks where the range is rendered as "full" or "-".
# Six capture groups: uniprot, chunk_type_a, range_a, chunk_type_b, gene, range_b.
CITE_RE = re.compile(
    r"\[chunk\s+"
    r"([A-Za-z0-9_-]+):"          # uniprot / accession
    r"([a-z_]+):"                  # chunk_type (first occurrence)
    r"([^:\]]+?):\s+"              # residue range (first occurrence)
    r"([a-z_]+)\s+"                # chunk_type (second occurrence)
    r"([A-Za-z0-9]+)\s+"           # gene symbol
    r"([^\]]+?)"                   # residue range (second occurrence)
    r"\]"
)

# Top-level proposal heading. Matches "## something" at column 0.
PROPOSAL_HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)

# Quoted text. Non-greedy, anything between straight double-quotes that does
# not itself contain a double quote or a newline.
QUOTE_RE = re.compile(r'"([^"\n]+)"')

# Look this many lines BEFORE a citation for nearby quoted text. The cookbook
# helper puts quotes on the same line as, or immediately preceding, their
# citation; 3 lines is a comfortable upper bound.
QUOTE_LOOKBACK_LINES = 3


def _norm_placeholder(rng: str) -> str:
    """`full` and `-` both denote a residue_start==residue_end==0 chunk."""
    return "" if rng.strip() in ("full", "-") else rng.strip()


def _to_range_tuple(rng: str) -> Optional[tuple[int, int]]:
    """Convert a residue-range string to (start, end). `full`/`-` -> (0, 0)."""
    s = rng.strip()
    if s in ("full", "-", ""):
        return (0, 0)
    m = re.match(r"^(\d+)-(\d+)$", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    # Single residue like "127" -- treat as (127, 127). Not strictly the schema
    # but tolerant of one-off cookbook outputs.
    m = re.match(r"^(\d+)$", s)
    if m:
        v = int(m.group(1))
        return (v, v)
    return None


def split_proposals(text: str) -> list[tuple[str, str]]:
    """Split PROPOSALS.md into (heading, body) pairs by top-level ## sections.

    Anything before the first ``## `` heading is returned as a synthetic
    ("(preamble)", ...) block so its citations are still audited.
    """
    headings = list(PROPOSAL_HEADING_RE.finditer(text))
    if not headings:
        return [("(whole file)", text)]

    blocks: list[tuple[str, str]] = []
    if headings[0].start() > 0:
        preamble = text[: headings[0].start()].strip()
        if preamble:
            blocks.append(("(preamble)", preamble))

    for i, h in enumerate(headings):
        start = h.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end]
        # First line of the block is the heading itself.
        first_nl = body.find("\n")
        if first_nl == -1:
            heading_line = body.strip()
        else:
            heading_line = body[:first_nl].strip()
        blocks.append((heading_line.lstrip("# ").strip() or "(unnamed)", body))
    return blocks


def find_nearby_quotes(block: str, citation_offset: int) -> list[str]:
    """Return double-quoted strings found in the QUOTE_LOOKBACK_LINES lines
    immediately preceding ``citation_offset`` (and on the citation's own line
    up to where the citation starts).
    """
    # Walk back QUOTE_LOOKBACK_LINES newlines from citation_offset.
    cursor = citation_offset
    newlines_seen = 0
    while cursor > 0 and newlines_seen <= QUOTE_LOOKBACK_LINES:
        cursor -= 1
        if block[cursor] == "\n":
            newlines_seen += 1
            if newlines_seen > QUOTE_LOOKBACK_LINES:
                cursor += 1  # don't include the newline before our window
                break
    window = block[cursor:citation_offset]
    return [m.group(1) for m in QUOTE_RE.finditer(window)]


def build_chunk_index(coll) -> tuple[
    dict[tuple, list[str]],
    dict[tuple, list[str]],
    dict[str, str],
]:
    """Pull every chunk's metadata + document text once, build lookup tables.

    Returns ``(idx_uniprot, idx_gene, docs_by_id)`` where the two indices map
    ``(key, chunk_type, residue_start, residue_end) -> [chunk_id, ...]`` -- one
    keyed by ``uniprot_id``, one keyed by ``gene`` symbol -- and
    ``docs_by_id`` maps each chunk id to its document text.
    """
    data = coll.get(include=["metadatas", "documents"])
    ids = data["ids"]
    metas = data["metadatas"]
    docs = data["documents"]

    idx_uniprot: dict[tuple, list[str]] = defaultdict(list)
    idx_gene: dict[tuple, list[str]] = defaultdict(list)
    docs_by_id: dict[str, str] = {}

    for cid, md, doc in zip(ids, metas, docs):
        u = md.get("uniprot_id", "") or ""
        g = md.get("gene", "") or ""
        ct = md.get("chunk_type", "") or ""
        try:
            rs = int(md.get("residue_start", 0) or 0)
        except (TypeError, ValueError):
            rs = 0
        try:
            re_ = int(md.get("residue_end", 0) or 0)
        except (TypeError, ValueError):
            re_ = 0
        idx_uniprot[(u, ct, rs, re_)].append(cid)
        idx_gene[(g, ct, rs, re_)].append(cid)
        docs_by_id[cid] = doc or ""

    return idx_uniprot, idx_gene, docs_by_id


def audit_proposals(
    proposals_path: Path,
    chroma_path: str,
    strict: bool,
) -> int:
    text = proposals_path.read_text(encoding="utf-8", errors="replace")

    client = chromadb.PersistentClient(path=chroma_path)
    coll = client.get_collection(COLLECTION)
    n_chunks = coll.count()
    print(f"Loaded collection {COLLECTION!r} from {chroma_path} ({n_chunks} chunks)")

    idx_uniprot, idx_gene, docs_by_id = build_chunk_index(coll)

    blocks = split_proposals(text)
    print(f"Parsed {len(blocks)} proposal block(s) from {proposals_path}")

    # Aggregate counters.
    total_proposals = len(blocks)
    total_citations = 0
    ok_proposals = 0
    warn_proposals = 0
    fail_proposals = 0
    ok_cites = 0
    warn_cites = 0
    fail_cites = 0

    for heading, body in blocks:
        cites = list(CITE_RE.finditer(body))
        if not cites:
            # A proposal block with zero citations is not a FAIL by itself --
            # could be a heading-only summary. Note it but treat as OK.
            print(f"\n## {heading}: 0 citations (no claims to audit)")
            ok_proposals += 1
            continue

        print(f"\n## {heading}: {len(cites)} citation(s)")
        block_fail = False
        block_warn = False

        for m in cites:
            total_citations += 1
            uniprot, ct_a, rng_a, ct_b, gene, rng_b = m.groups()
            raw = m.group(0)

            # Internal consistency: the two halves of the citation must agree.
            if _norm_placeholder(rng_a) != _norm_placeholder(rng_b):
                print(f"  FAIL {raw}")
                print(f"       residue_range mismatch within citation "
                      f"({rng_a!r} vs {rng_b!r})")
                fail_cites += 1
                block_fail = True
                continue
            if ct_a != ct_b:
                print(f"  FAIL {raw}")
                print(f"       chunk_type mismatch within citation "
                      f"({ct_a!r} vs {ct_b!r})")
                fail_cites += 1
                block_fail = True
                continue

            rng = _to_range_tuple(rng_a)
            if rng is None:
                print(f"  FAIL {raw}")
                print(f"       un-parseable residue range {rng_a!r}")
                fail_cites += 1
                block_fail = True
                continue

            rs, re_end = rng
            key_u = (uniprot, ct_a, rs, re_end)
            key_g = (gene, ct_a, rs, re_end)

            hit_ids = idx_uniprot.get(key_u, []) or idx_gene.get(key_g, [])
            if not hit_ids:
                print(f"  FAIL {raw}")
                print(f"       no chunk in chroma with uniprot_id={uniprot!r} "
                      f"OR gene={gene!r} matching chunk_type={ct_a!r} "
                      f"residue_start={rs} residue_end={re_end}")
                fail_cites += 1
                block_fail = True
                continue

            # Citation resolves. Now check any nearby quotes.
            quotes = find_nearby_quotes(body, m.start())
            chunk_texts = [docs_by_id.get(cid, "") for cid in hit_ids]
            unmatched_quotes = []
            for q in quotes:
                if not any(q in ct for ct in chunk_texts):
                    unmatched_quotes.append(q)

            if not unmatched_quotes:
                print(f"  OK   {raw}")
                ok_cites += 1
            else:
                tag = "FAIL" if strict else "WARN"
                print(f"  {tag} {raw}")
                for q in unmatched_quotes:
                    snippet = q if len(q) < 80 else q[:77] + "..."
                    print(f"       quote not a verbatim substring of cited chunk: {snippet!r}")
                if strict:
                    fail_cites += 1
                    block_fail = True
                else:
                    warn_cites += 1
                    block_warn = True

        if block_fail:
            fail_proposals += 1
        elif block_warn:
            warn_proposals += 1
        else:
            ok_proposals += 1

    # Final report.
    print("\n=== AUDIT SUMMARY ===")
    print(f"  proposals:  total={total_proposals}  ok={ok_proposals}  "
          f"warn={warn_proposals}  fail={fail_proposals}")
    print(f"  citations:  total={total_citations}  ok={ok_cites}  "
          f"warn={warn_cites}  fail={fail_cites}")
    print(f"  mode:       {'strict (WARN promoted to FAIL)' if strict else 'lenient (paraphrase tolerated)'}")
    print(f"  chroma:     {chroma_path}")
    print(f"  proposals:  {proposals_path}")

    return 0 if fail_cites == 0 else 1


def default_chroma_dir() -> str:
    """Resolve the g2p-rag Chroma directory without a developer-local path."""
    env = os.environ.get("G2P_INDEX_DIR") or os.environ.get("G2P_CHROMA_PATH")
    if env:
        return env
    return str(Path(__file__).resolve().parents[2] / "g2p-rag" / "data" / "chroma")


def main(argv: Optional[list[str]] = None) -> int:
    default_chroma = default_chroma_dir()
    ap = argparse.ArgumentParser(
        description=(
            "Audit chunk citations in a PROPOSALS.md against the g2p-rag "
            "Chroma collection. Confirms each cited chunk exists, and that "
            "nearby quoted text is a verbatim substring of the chunk."
        )
    )
    ap.add_argument("proposals", type=Path, help="path to PROPOSALS.md")
    ap.add_argument(
        "--chroma-path",
        default=default_chroma,
        help=(
            "override the Chroma persist directory "
            f"(default: G2P_INDEX_DIR/G2P_CHROMA_PATH or {default_chroma})"
        ),
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="treat unmatched quotes (WARN) as FAILs -- no paraphrase tolerated",
    )
    args = ap.parse_args(argv)

    if not args.proposals.exists():
        print(f"error: {args.proposals} not found", file=sys.stderr)
        return 2

    return audit_proposals(args.proposals, args.chroma_path, args.strict)


if __name__ == "__main__":
    sys.exit(main())
