"""Run all 10 blinded YAML benchmark cases through the real `therapy-agent`
LangGraph pipeline with a local Llama backend, and score against the
expected target / modality / citations.

Usage:
    .venv/Scripts/python.exe run_blinded.py
    .venv/Scripts/python.exe run_blinded.py --only ekterly_serping1
    .venv/Scripts/python.exe run_blinded.py --out blinded_results.json
    .venv/Scripts/python.exe run_blinded.py --baselines-only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("THERAPY_AGENT_LLM_BACKEND", "llama")

import yaml  # noqa: E402

from collections import Counter  # noqa: E402

from therapy_agent.graph import run_agent  # noqa: E402


async def run_agent_self_consistent(gene: str, mutation: str, disease_phenotype: str,
                                    n_samples: int = 1):
    """Run the full agent pipeline n_samples times and majority-vote on the
    final target_protein. Returns the (vote-winning) final state.

    Self-consistency on the FULL pipeline (not just Stage 2 of synthesis)
    catches cases where the LLM picks different targets across independent
    runs due to temperature, ordering of tool calls, or self-critique
    realignment.

    The chosen state's `strategy.confidence_score` is REPLACED by the vote
    margin (winner_votes / n_samples). v0.8's calibration analysis found
    the LLM's self-reported confidence has ECE 0.2-0.4 (poorly calibrated,
    systematically under-confident). Vote-margin confidence is more honest
    -- it directly reflects how often N independent samples agreed.
    """
    if n_samples <= 1:
        return await run_agent(gene, mutation, disease_phenotype)

    states = await asyncio.gather(*[
        run_agent(gene, mutation, disease_phenotype)
        for _ in range(n_samples)
    ])
    # Vote on the canonical HGNC symbol of the final target.
    votes = Counter()
    for st in states:
        t = ((st.get("strategy") or {}).get("target_protein") or "").strip()
        m = re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", t)
        canonical = (m.group(0) if m else t).upper()
        if canonical:
            votes[canonical] += 1
    if not votes:
        return states[0]
    winner_canonical, winner_n = votes.most_common(1)[0]
    vote_margin = winner_n / n_samples  # 3/3 -> 1.0; 2/3 -> 0.67; 1/3 -> 0.33

    # Return the first state whose canonical target matches the winner.
    for st in states:
        t = ((st.get("strategy") or {}).get("target_protein") or "").strip()
        m = re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", t)
        canonical = (m.group(0) if m else t).upper()
        if canonical == winner_canonical:
            chosen = dict(st)
            chosen["self_consistency_votes"] = dict(votes)
            # Replace LLM self-reported confidence with the vote margin,
            # which is empirically better calibrated.
            strat = dict(chosen.get("strategy") or {})
            strat["confidence_score"] = vote_margin
            strat["confidence_source"] = f"vote_margin({winner_n}/{n_samples})"
            chosen["strategy"] = strat
            final_strat = dict(chosen.get("final_strategy") or strat)
            final_strat["confidence_score"] = vote_margin
            final_strat["confidence_source"] = f"vote_margin({winner_n}/{n_samples})"
            chosen["final_strategy"] = final_strat
            return chosen
    return states[0]


# ── locate the therapy-agent sibling repo ─────────────────────────────────────

def _find_therapy_agent_root() -> Path:
    """Locate `therapy-agent` next to `therapy-stack` (or via env var)."""
    env = os.environ.get("THERAPY_AGENT_ROOT")
    if env:
        p = Path(env).resolve()
        if p.exists():
            return p
    # repo layout: <parent>/therapy-stack/sandbox/run_blinded.py
    here = Path(__file__).resolve()
    sibling = here.parent.parent.parent / "therapy-agent"
    if sibling.exists():
        return sibling
    raise FileNotFoundError(
        "Could not locate therapy-agent. Set THERAPY_AGENT_ROOT env var or "
        "place therapy-agent next to therapy-stack."
    )


_THERAPY_AGENT_ROOT = _find_therapy_agent_root()
_PRIMARY_DIR = _THERAPY_AGENT_ROOT / "benchmarks"                       # primary (Ekterly + BRD4780)
_SUPP_DIR    = _THERAPY_AGENT_ROOT / "benchmarks" / "cases"             # supplementary dev set
_HELDOUT_DIR = _THERAPY_AGENT_ROOT / "benchmarks" / "heldout_2024_2025" # post-cutoff val set
_ADV_DIR     = _THERAPY_AGENT_ROOT / "benchmarks" / "adversarial"       # adversarial probes


# ── case loading ──────────────────────────────────────────────────────────────

def load_cases(set_name: str = "dev") -> list[dict]:
    """Load benchmark cases by named split.

    set_name:
      - "dev" (default): primary + supplementary (16 cases, used for iteration).
      - "val": post-2024 held-out set (FDA approvals after Llama / R1-Distill
        training cutoff -- the closest thing we have to a true generalization
        test).
      - "all": dev + val combined.
    """
    dirs: list = []
    if set_name in ("dev", "all"):
        dirs += [_PRIMARY_DIR, _SUPP_DIR]
    if set_name in ("val", "all"):
        dirs.append(_HELDOUT_DIR)
    if set_name in ("adversarial", "all"):
        dirs.append(_ADV_DIR)
    if not dirs:
        raise ValueError(f"Unknown set {set_name!r}; use dev|val|adversarial|all.")
    cases: list[dict] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data and "input" in data and "expected_outputs" in data:
                data["_file"] = str(p.relative_to(_THERAPY_AGENT_ROOT))
                if d == _HELDOUT_DIR:
                    data["_set"] = "val"
                elif d == _ADV_DIR:
                    data["_set"] = "adversarial"
                else:
                    data["_set"] = "dev"
                cases.append(data)
    return cases


# ── scoring ───────────────────────────────────────────────────────────────────

# Tokens that often appear ALL-CAPS but are NOT HGNC symbols. Including
# these as match candidates would produce false positives (e.g. predicting
# "AAV9 delivery" against a Zolgensma gold target string that mentions AAV9).
_NON_HGNC_BLOCKLIST = {
    "DNA", "RNA", "MRNA", "MIRNA", "SIRNA", "ASO", "PMO", "ATP", "GTP",
    "ADP", "GDP", "CAMP", "AAV", "AAV9", "LNP", "GALNAC", "PCR", "PNS",
    "CNS", "UPR", "ER", "GOLGI", "CAAX", "RT", "PTM", "PK", "PD", "FDA",
    "ICH", "ICMT", "NEJM", "PMID", "DOI", "HGNC",
}


def _symbols(text: str) -> set[str]:
    """Extract HGNC-shaped symbols, filtering out known non-gene tokens."""
    raw = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text or ""))
    return {s for s in raw if s.upper() not in _NON_HGNC_BLOCKLIST}


def score_target(predicted: str, expected: dict) -> dict:
    """Multi-target overlap check.

    A prediction counts as recovered if it matches:
      1. the curator's primary `target_protein` (exact / substring / symbol),
      2. any non-generic alias in `target_aliases`, OR
      3. any of the disease's other FDA-validated targets listed under
         `valid_targets` (the multi-target set). This is the principled fix
         for diseases like SCD (voxelotor / HBB vs Casgevy / BCL11A) or HAE
         (Ekterly / KLKB1 vs Garadacimab / F12 vs Firazyr / BDKRB2). Any
         FDA-approved target is a defensible answer.

    `matched_via_kind` is one of {'primary', 'alias', 'valid_target'} so the
    downstream report can distinguish "recovered the named drug's target"
    from "recovered a different but FDA-validated target for the same
    disease".
    """
    pred = (predicted or "").lower()
    if not pred:
        return {"recovered": False, "matched_via": None, "matched_via_kind": None}

    exp_target = (expected.get("target_protein") or "").lower()
    if exp_target and exp_target in pred:
        return {"recovered": True, "matched_via": expected["target_protein"],
                "matched_via_kind": "primary"}

    aliases = [a.lower() for a in (expected.get("target_aliases") or [])]
    for a in aliases:
        if not a:
            continue
        if a in pred and not _is_generic_alias(a):
            return {"recovered": True, "matched_via": a,
                    "matched_via_kind": "alias"}

    pred_symbols = _symbols(predicted or "")
    exp_symbols = _symbols(expected.get("target_protein") or "")
    common = pred_symbols & exp_symbols
    if common:
        return {"recovered": True, "matched_via": next(iter(common)),
                "matched_via_kind": "primary"}

    # Multi-target acceptance: other FDA-validated targets for the same disease.
    valid = [(v or "").lower() for v in (expected.get("valid_targets") or [])]
    for vt in valid:
        if not vt:
            continue
        if vt in pred and not _is_generic_alias(vt):
            return {"recovered": True, "matched_via": vt,
                    "matched_via_kind": "valid_target"}
    # Symbol match against valid_targets too
    for vt_raw in (expected.get("valid_targets") or []):
        vt_symbols = _symbols(vt_raw)
        common = pred_symbols & vt_symbols
        if common:
            return {"recovered": True, "matched_via": next(iter(common)),
                    "matched_via_kind": "valid_target"}

    return {"recovered": False, "matched_via": None, "matched_via_kind": None}


_GENERIC_ALIASES = {
    "gene therapy", "gene replacement", "asogene therapy", "exon skipping",
    "antisense", "antisense oligonucleotide", "small molecule", "antibody",
    "mab", "monoclonal antibody", "sirna", "aso", "modulator",
    "chaperone", "agonist", "inhibitor", "activator", "stabilizer",
}


def _is_generic_alias(alias: str) -> bool:
    a = alias.strip().lower()
    return a in _GENERIC_ALIASES or len(a) < 3


def score_modality(predicted_modality: str, expected: dict) -> bool:
    """Light modality match: tokenize expected modulation_type and predicted
    modality strings; require overlap on a normalized class."""
    exp = (expected.get("modulation_type") or "").lower()
    pred = (predicted_modality or "").lower()
    if not exp or not pred:
        return False
    # Common synonyms by canonical class.
    classes = {
        "inhibitor": {"inhibitor", "antagonist", "blocker", "anti-"},
        "activator": {"activator", "agonist", "potentiator"},
        "siRNA_ASO": {"sirna", "aso", "antisense", "knockdown", "rnai",
                      "splice_modifier", "splice modulator", "splice-modulator"},
        "gene_therapy": {"gene therapy", "gene_therapy", "gene addition",
                         "aav", "transgene"},
        "chaperone": {"chaperone", "pharmacological chaperone", "stabilizer"},
        "replacement": {"replacement", "enzyme replacement"},
    }
    # Find which canonical classes the expected and predicted strings hit.
    def _classes_of(s: str) -> set[str]:
        out: set[str] = set()
        for cls, kws in classes.items():
            for kw in kws:
                if kw in s:
                    out.add(cls)
                    break
        return out
    return bool(_classes_of(exp) & _classes_of(pred))


def score_citation(rationale: str, precedent_drugs: list[str],
                   citations: list[str], expected: dict) -> bool:
    """Did the model mention any of the case's key citations or drug names?"""
    haystack = " ".join([
        rationale or "",
        " ".join(precedent_drugs or []),
        " ".join(citations or []),
    ]).lower()
    keys = [k.lower() for k in expected.get("key_citations") or []]
    return any(k in haystack for k in keys if k)


# ── baselines ─────────────────────────────────────────────────────────────────

def baseline_always_disease_gene(case: dict) -> dict:
    """Trivial baseline: predict the disease gene as the target. Useful
    sanity-check — for cases where target == disease gene this baseline
    succeeds without any reasoning."""
    pred = case["input"]["gene"]
    return score_target(pred, case["expected_outputs"])


def baseline_first_reactome_interactor(case: dict) -> dict:
    """Baseline: predict the FIRST listed Reactome interactor of the disease
    gene. Captures naive "pick something downstream" behavior."""
    try:
        from therapy_agent.tools.reactome_query import GENE_PATHWAY_FALLBACK
    except ImportError:
        return {"recovered": False, "matched_via": None}
    gene = case["input"]["gene"].upper()
    entry = GENE_PATHWAY_FALLBACK.get(gene, {})
    interactors = entry.get("interactors", []) or []
    if not interactors:
        return {"recovered": False, "matched_via": None}
    return score_target(interactors[0], case["expected_outputs"])


# ── statistical helpers ───────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% confidence interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ── main async loop ───────────────────────────────────────────────────────────

async def main_async(args) -> int:
    cases = load_cases(args.set)
    if args.only:
        wanted = {w.strip() for w in args.only.split(",") if w.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[:args.limit]

    print(f"Running {len(cases)} cases ({args.set} set) with therapy-agent backend "
          f"= {os.environ.get('THERAPY_AGENT_LLM_BACKEND', '?')}.\n")

    # Compute baselines first — they're free.
    base_dg = [baseline_always_disease_gene(c) for c in cases]
    base_rx = [baseline_first_reactome_interactor(c) for c in cases]
    print(f"Baselines (no LLM):")
    print(f"  always-predict-disease-gene:     {sum(b['recovered'] for b in base_dg)}/{len(cases)}")
    print(f"  first-Reactome-interactor:        {sum(b['recovered'] for b in base_rx)}/{len(cases)}")
    print()

    if args.baselines_only:
        return 0

    results: list[dict] = []
    t_start = time.time()
    for i, case in enumerate(cases, 1):
        cid = case["id"]
        inp = case["input"]
        exp = case["expected_outputs"]
        print(f"[{i}/{len(cases)}] {cid}")
        print(f"    gene={inp['gene']}  mut={inp['mutation'][:60]!r}")

        t0 = time.time()
        try:
            state = await run_agent_self_consistent(
                gene=inp["gene"],
                mutation=inp["mutation"],
                disease_phenotype=inp["disease_phenotype"],
                n_samples=args.self_consistency,
            )
            elapsed = time.time() - t0
            strat = state.get("strategy") or {}
            pred = strat.get("target_protein") or ""
            mod_pred = strat.get("modulation_type", "") or ""
            conf = float(strat.get("confidence_score", 0.0) or 0.0)
            rationale = strat.get("rationale", "") or ""
            precedent = strat.get("precedent_drugs", []) or []
            cits = strat.get("citations", []) or []

            target_ok = score_target(pred, exp)
            modality_ok = score_modality(mod_pred, exp)
            citation_ok = score_citation(rationale, precedent, cits, exp)
            conf_ok = conf >= float(exp.get("min_confidence", 0.0) or 0.0)

            flag = "OK " if target_ok["recovered"] else "MISS"
            print(f"    -> {flag}  pred={pred!r}  expected={exp['target_protein']}")
            print(f"       modality_ok={modality_ok}  citation_ok={citation_ok}  "
                  f"conf_ok={conf_ok}  conf={conf:.2f}  ({elapsed:.1f}s)")
            # Aggregate token usage across all LLM calls in this case.
            tu = state.get("token_usage") or []
            total_in = sum(int(t.get("input_tokens", 0) or 0) for t in tu)
            total_out = sum(int(t.get("output_tokens", 0) or 0) for t in tu)
            per_node = {}
            for t in tu:
                per_node[t.get("node", "?")] = per_node.get(t.get("node", "?"), 0) + 1
            results.append({
                "case_id": cid,
                "set": case.get("_set", "dev"),
                "gene": inp["gene"],
                "expected_target": exp["target_protein"],
                "expected_aliases": exp.get("target_aliases", []),
                "expected_mechanism": exp.get("mechanism_class"),
                "expected_modulation": exp.get("modulation_type", ""),
                "expected_min_confidence": exp.get("min_confidence", 0.0),
                "expected_key_citations": exp.get("key_citations", []),
                "predicted_target": pred,
                "predicted_modulation": mod_pred,
                "predicted_mechanism": state.get("molecular_mechanism"),
                "predicted_confidence": conf,
                "predicted_rationale": rationale,
                "predicted_precedent_drugs": precedent,
                "predicted_citations": cits,
                "target_recovered": target_ok["recovered"],
                "target_matched_via": target_ok["matched_via"],
                "target_matched_via_kind": target_ok.get("matched_via_kind"),
                "self_consistency_votes": state.get("self_consistency_votes"),
                "modality_recovered": modality_ok,
                "citation_recovered": citation_ok,
                "confidence_meets_min": conf_ok,
                "elapsed_s": round(elapsed, 1),
                # Cost / latency telemetry -- production teams should track per
                # case so prompt changes and model swaps can be cost-budgeted.
                "tokens_in_total": total_in,
                "tokens_out_total": total_out,
                "llm_calls_per_node": per_node,
            })
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"    -> ERROR {exc} ({elapsed:.1f}s)")
            results.append({
                "case_id": cid,
                "gene": inp["gene"],
                "expected_target": exp["target_protein"],
                "predicted_target": "",
                "target_recovered": False,
                "modality_recovered": False,
                "citation_recovered": False,
                "confidence_meets_min": False,
                "error": str(exc),
                "elapsed_s": round(elapsed, 1),
            })
        print()

    total = time.time() - t_start

    n = len(results)
    target_n = sum(1 for r in results if r.get("target_recovered"))
    modality_n = sum(1 for r in results if r.get("modality_recovered"))
    citation_n = sum(1 for r in results if r.get("citation_recovered"))
    full_n = sum(1 for r in results
                 if r.get("target_recovered")
                 and r.get("modality_recovered")
                 and r.get("citation_recovered"))

    # Disease-gene-default rate: fraction of predictions where the model
    # output the disease gene as the target, regardless of whether that's
    # correct. A high rate on cases where the EXPECTED target is the
    # disease gene is fine; a high rate on cases where the expected target
    # is NOT the disease gene is the dominant val failure mode (v0.8
    # miss-taxonomy: 100% of R1-Distill val misses were this).
    def _canon(t: str) -> str:
        if not t:
            return ""
        m = re.search(r"\b[A-Z][A-Z0-9]{1,9}\b", t)
        return (m.group(0) if m else t.strip()).upper()

    dg_pred_when_should_diverge = 0
    n_diverge_cases = 0
    dg_pred_total = 0
    for r in results:
        pred_canon = _canon(r.get("predicted_target") or "")
        gene_canon = _canon(r.get("gene") or "")
        exp_canon = _canon(r.get("expected_target") or "")
        if pred_canon and pred_canon == gene_canon:
            dg_pred_total += 1
        if gene_canon and exp_canon and gene_canon != exp_canon:
            n_diverge_cases += 1
            if pred_canon == gene_canon:
                dg_pred_when_should_diverge += 1
    dg_default_rate = (dg_pred_when_should_diverge / n_diverge_cases
                       if n_diverge_cases else 0.0)

    lo, hi = wilson_ci(target_n, n) if n else (0.0, 0.0)
    print(f"=== Target-recovery: {target_n}/{n} (95% Wilson CI {lo*100:.0f}–{hi*100:.0f}%) "
          f"({total:.0f}s total) ===")
    print(f"    Modality-also-correct:   {modality_n}/{n}")
    print(f"    Citation-also-correct:   {citation_n}/{n}")
    print(f"    Full (target+modality+citation): {full_n}/{n}")
    print(f"    Baseline disease-gene:  {sum(b['recovered'] for b in base_dg)}/{n}")
    print(f"    Baseline 1st interactor:{sum(b['recovered'] for b in base_rx)}/{n}")
    print(f"    Disease-gene-default rate (when expected differs): "
          f"{dg_pred_when_should_diverge}/{n_diverge_cases} "
          f"({dg_default_rate*100:.0f}%)")
    print()

    if args.out:
        Path(args.out).write_text(json.dumps({
            "backend": os.environ.get("THERAPY_AGENT_LLM_BACKEND", "anthropic"),
            "model_path": os.environ.get("LLAMA_MODEL_PATH", ""),
            "n_cases": n,
            "target_recovered": target_n,
            "modality_recovered": modality_n,
            "citation_recovered": citation_n,
            "full_recovered": full_n,
            "wilson_ci_target": [lo, hi],
            "baseline_disease_gene_recovered": sum(b["recovered"] for b in base_dg),
            "baseline_first_interactor_recovered": sum(b["recovered"] for b in base_rx),
            "disease_gene_default_rate": dg_default_rate,
            "disease_gene_default_when_should_diverge": dg_pred_when_should_diverge,
            "disease_gene_default_diverge_cases": n_diverge_cases,
            "disease_gene_predicted_total": dg_pred_total,
            "total_seconds": round(total, 1),
            "results": results,
        }, indent=2), encoding="utf-8")
        print(f"Wrote {args.out}")
    return 0 if target_n == n else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=str, default="dev",
                    choices=["dev", "val", "adversarial", "all"],
                    help="Which split to run. dev = primary + supplementary "
                         "(used for iteration); val = post-2024 held-out "
                         "(true generalization test); adversarial = "
                         "hand-crafted failure-mode probes; all = combined.")
    ap.add_argument("--only", type=str, default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("blinded_results.json"))
    ap.add_argument("--baselines-only", action="store_true")
    ap.add_argument("--self-consistency", type=int, default=1,
                    help="Run the full pipeline N times per case and "
                         "majority-vote the final target (default 1 = no "
                         "self-consistency).")
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
