"""
Deterministic scorer.

Stands in for `bio-rag-eval.score_case(...)` in the architecture. We
deliberately use a *deterministic* judge here rather than an LLM judge,
because:
  (a) we want the e2e demo's correctness to be reproducible across runs, and
  (b) bringing in an LLM judge would require another model and another
      ~2 GB of disk.

A predicted strategy is considered correct if any of its declared
target token(s) appears as a substring of the gold target text, after a
small set of normalizations (case-fold, drop UniProt accessions in
parens, collapse whitespace). The gold target text often contains the
HGNC symbol explicitly — e.g. "P53779 (PCSK9) — proprotein convertase
subtilisin/kexin type 9 mRNA" — so substring matching on the symbol is
both simple and faithful.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from agent import Strategy


@dataclass
class CaseScore:
    case_id: str
    disease: str
    causal_gene: str
    gold_target: str
    predicted_top_target: str
    rank_of_correct: int | None
    recovered: bool
    n_strategies: int


_UPROT_PAREN = re.compile(r"\([A-Z][0-9][A-Z0-9]{3}[0-9]\)")
_NONWORD = re.compile(r"[^a-z0-9 ]+")

# Common ALL-CAPS tokens that look like HGNC symbols but aren't. Excluding
# these keeps the matcher from scoring a recovery when both expected and
# predicted strings happen to mention generic abbreviations like "RNA"
# or delivery-vector names like "AAV9".
_NON_HGNC_BLOCKLIST = {
    "DNA", "RNA", "MRNA", "MIRNA", "SIRNA", "ASO", "PMO", "ATP", "GTP",
    "ADP", "GDP", "CAMP", "AAV", "AAV9", "LNP", "GALNAC", "PCR", "PNS",
    "CNS", "UPR", "ER", "GOLGI", "CAAX", "RT", "PTM", "PK", "PD", "FDA",
}


def _norm(s: str) -> str:
    s = s.lower()
    s = _UPROT_PAREN.sub(" ", s)
    s = _NONWORD.sub(" ", s)
    return " ".join(s.split())


def _symbols(text: str) -> set[str]:
    raw = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text or ""))
    return {s for s in raw if s not in _NON_HGNC_BLOCKLIST}


def _gold_tokens(gold: str) -> set[str]:
    norm = _norm(gold)
    symbols = _symbols(gold)
    return set(norm.split()) | {s.lower() for s in symbols}


def _is_match(predicted: str, gold_tokens: set[str], gold_symbols: set[str]) -> bool:
    if not predicted:
        return False
    pred_norm_tokens = set(_norm(predicted).split())
    pred_symbols = {s.lower() for s in _symbols(predicted)}

    if pred_symbols & gold_symbols:
        return True

    filler = {"mrna", "protein", "gene", "the", "a", "an", "of", "and",
              "for", "to", "in", "is", "with", "via"}
    overlap = (pred_norm_tokens & gold_tokens) - filler
    return len(overlap) >= 2


def score(case_id: str, disease: str, causal_gene: str, gold_target: str,
          strategies: list[Strategy]) -> CaseScore:
    gold_tokens = _gold_tokens(gold_target)
    gold_symbols = {s.lower() for s in _symbols(gold_target)}

    rank: int | None = None
    for i, s in enumerate(strategies, start=1):
        if _is_match(s.target, gold_tokens, gold_symbols):
            rank = i
            break
    top = strategies[0].target if strategies else ""
    return CaseScore(
        case_id=case_id,
        disease=disease,
        causal_gene=causal_gene,
        gold_target=gold_target,
        predicted_top_target=top,
        rank_of_correct=rank,
        recovered=rank is not None,
        n_strategies=len(strategies),
    )
