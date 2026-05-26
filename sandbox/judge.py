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


def _norm(s: str) -> str:
    s = s.lower()
    s = _UPROT_PAREN.sub(" ", s)
    s = _NONWORD.sub(" ", s)
    return " ".join(s.split())


def _gold_tokens(gold: str) -> set[str]:
    """Extract identifying tokens from the gold target string.

    Examples:
      "P53779 (PCSK9) -- proprotein convertase subtilisin/kexin type 9 mRNA"
        -> {"pcsk9", "proprotein", "convertase", ...}
      "BCL11A erythroid enhancer (chr2:...) -- transcriptional repressor of
       fetal hemoglobin"
        -> {"bcl11a", "erythroid", "enhancer", "fetal", "hemoglobin", ...}
    """
    norm = _norm(gold)
    # Pull out HGNC-like all-caps symbols from the *original* string too.
    symbols = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", gold))
    return set(norm.split()) | {s.lower() for s in symbols}


def _is_match(predicted: str, gold_tokens: set[str], gold_symbols: set[str]) -> bool:
    if not predicted:
        return False
    pred_norm_tokens = set(_norm(predicted).split())
    # Pull HGNC-shaped symbols out of the prediction.
    pred_symbols = {s.lower() for s in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", predicted)}

    # A hit on an HGNC symbol is the strongest signal — that's our primary criterion.
    if pred_symbols & gold_symbols:
        return True

    # Otherwise require at least two content-word tokens in common AND not
    # just generic "mrna" / "protein" filler.
    filler = {"mrna", "protein", "gene", "the", "a", "an", "of", "and",
              "for", "to", "in", "is", "with", "via"}
    overlap = (pred_norm_tokens & gold_tokens) - filler
    return len(overlap) >= 2


def score(case_id: str, disease: str, causal_gene: str, gold_target: str,
          strategies: list[Strategy]) -> CaseScore:
    gold_tokens = _gold_tokens(gold_target)
    gold_symbols = {s.lower() for s in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", gold_target)}

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
