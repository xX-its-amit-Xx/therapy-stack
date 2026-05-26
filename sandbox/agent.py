"""
Therapy-target agent.

Given a disease, a causal gene, and biological context, asks the local
Llama-3.2-3B-Instruct model to propose a ranked list of therapeutic
targets and modalities. The agent never sees the gold answer.

This stands in for `therapy-agent.propose(...)` in the therapy-stack
architecture diagram. The contract — gene + context in, ranked
TherapeuticStrategy out — matches what ARCHITECTURE.md describes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from llama_cpp import Llama


SYSTEM = """You are a translational drug-discovery scientist.

You are given a disease, the causal disease gene, and biological context
(UniProt FUNCTION, PATHWAY, SUBUNIT, PTM, DISEASE, KEYWORDS, LIPIDATION).

Your task: propose up to THREE distinct therapeutic strategies, ranked
by how directly each addresses the underlying molecular mechanism.

THINK BEFORE PROPOSING. Walk through these questions in order. For each
that applies, the answer is often a better target than the disease gene
itself.

  1. LOSS-OF-FUNCTION vs GAIN-OF-TOXIC-FUNCTION?
       Loss → replace the protein, deliver the gene, upregulate a paralog,
              or fix splicing of a paralog.
       Toxic gain → knock down the mRNA (ASO / siRNA), or block a
                    downstream effector that mediates the toxicity.

  2. Is the disease protein POST-TRANSLATIONALLY MODIFIED (farnesylation,
     geranylgeranylation, palmitoylation, glycosylation), and does that
     modification CAUSE the pathology? Then the MODIFYING ENZYME is the
     target — not the disease protein. If the PTM section mentions a
     specific transferase that performs the modification, name THAT
     enzyme as the target.

  3. Is the broken enzyme DOWNSTREAM in a biosynthetic pathway whose
     UPSTREAM SUBSTRATE accumulates and is toxic? Then knock down the
     RATE-LIMITING UPSTREAM ENZYME to drain the substrate. The
     rate-limiting enzyme is the one that controls flux into the
     pathway, typically the first committed step.

  4. Is there a TRANSCRIPTIONAL REPRESSOR controlling a FUNCTIONAL PARALOG
     (e.g. a fetal vs adult isoform) that could compensate? Disrupt the
     repressor to reactivate the paralog.

  5. Does another protein CONTROL THE LEVEL of the disease protein by
     promoting its degradation, internalization, or proteolytic cleavage?
     Block that regulator to raise the disease protein back to normal.

  6. Otherwise, when the molecule is loss-of-function and not rescuable
     upstream, target the gene/RNA directly via gene therapy, mRNA
     replacement, chaperone, or splicing modulator.

OUTPUT — strict:

A strategy has:
  - target: a specific HGNC symbol (e.g. "PCSK9", "FNTB", "ALAS1"),
    "GENE (mRNA)" for RNA targets (e.g. "TTR (mRNA)"), or a descriptive
    name for genomic regulatory elements (e.g. "BCL11A erythroid enhancer").
  - modality: one of [small_molecule, antibody, ASO, siRNA, gene_therapy,
    crispr, modulator, chaperone, protein_replacement, other].
  - rationale: 1-2 sentences naming the mechanism by which hitting this
    target corrects or compensates the disease.
  - confidence: a number in [0, 1].

Do NOT default to "fix the broken gene" when a question above clearly
points to a better target.

Respond with ONLY a JSON object — no markdown fences, no commentary:
{
  "strategies": [
    {"target": "...", "modality": "...", "rationale": "...", "confidence": 0.0},
    ...
  ]
}
"""


@dataclass
class Strategy:
    target: str
    modality: str
    rationale: str
    confidence: float


class TherapyAgent:
    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int = 8,
                 seed: int = 7):
        self.model_path = model_path
        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            seed=seed,
            verbose=False,
        )

    def propose(self, *, disease: str, gene: str, context: str,
                temperature: float = 0.2, max_tokens: int = 600) -> list[Strategy]:
        user = (
            f"DISEASE: {disease}\n"
            f"CAUSAL GENE: {gene}\n\n"
            f"BIOLOGICAL CONTEXT:\n{context}\n\n"
            "Return JSON only."
        )
        resp = self._llm.create_chat_completion(
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = resp["choices"][0]["message"]["content"]
        return _parse(text)


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _parse(text: str) -> list[Strategy]:
    """Best-effort JSON parse from a possibly-noisy LLM response."""
    # 1) Try direct.
    candidates: list[str] = [text.strip()]
    # 2) Strip markdown fences.
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    # 3) First {...} block.
    m = _JSON_BLOCK_RE.search(text)
    if m:
        candidates.append(m.group(0))

    for c in candidates:
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        strategies = obj.get("strategies")
        if not isinstance(strategies, list):
            continue
        out: list[Strategy] = []
        for s in strategies:
            if not isinstance(s, dict):
                continue
            try:
                conf = float(s.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            out.append(Strategy(
                target=str(s.get("target", "")).strip(),
                modality=str(s.get("modality", "")).strip(),
                rationale=str(s.get("rationale", "")).strip(),
                confidence=conf,
            ))
        if out:
            return out
    return []


def strategy_to_dict(s: Strategy) -> dict:
    return asdict(s)
