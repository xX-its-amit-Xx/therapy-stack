"""Run all 10 blinded YAML benchmark cases through the real `therapy-agent`
LangGraph pipeline with a local Llama backend, and score against the
expected target.

Usage:
    .venv/Scripts/python.exe run_blinded.py
    .venv/Scripts/python.exe run_blinded.py --only ekterly_serping1
    .venv/Scripts/python.exe run_blinded.py --out blinded_results.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows.
sys.stdout.reconfigure(encoding="utf-8")

# Default to local Llama backend; the agent reads this on first call.
os.environ.setdefault("THERAPY_AGENT_LLM_BACKEND", "llama")

import yaml  # noqa: E402

from therapy_agent.graph import run_agent  # noqa: E402


_THERAPY_AGENT_ROOT = Path(
    "D:/Users/ashenoy00000/.windsurf/therapy-agent"
).resolve()
_PRIMARY_DIR = _THERAPY_AGENT_ROOT / "benchmarks"
_SUPP_DIR = _THERAPY_AGENT_ROOT / "benchmarks" / "cases"


def load_cases() -> list[dict]:
    """Load all 10 cases from the therapy-agent benchmarks dir."""
    cases: list[dict] = []
    for d in (_PRIMARY_DIR, _SUPP_DIR):
        for p in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data and "input" in data and "expected_outputs" in data:
                data["_file"] = str(p.relative_to(_THERAPY_AGENT_ROOT))
                cases.append(data)
    return cases


def score(predicted: str, expected: dict) -> dict:
    """Boolean match: does the predicted target match the expected target or
    any of its declared aliases? Case-insensitive substring."""
    pred = (predicted or "").lower()
    if not pred:
        return {"recovered": False, "matched_via": None}
    exp = (expected.get("target_protein") or "").lower()
    aliases = [a.lower() for a in (expected.get("target_aliases") or [])]
    if exp and exp in pred:
        return {"recovered": True, "matched_via": expected["target_protein"]}
    for a in aliases:
        if a and a in pred:
            return {"recovered": True, "matched_via": a}
    # Symmetric: maybe the prediction symbol is contained in the expected target field
    pred_symbols = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", predicted or ""))
    exp_symbols = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b",
                                 expected.get("target_protein") or ""))
    if pred_symbols & exp_symbols:
        sym = next(iter(pred_symbols & exp_symbols))
        return {"recovered": True, "matched_via": sym}
    return {"recovered": False, "matched_via": None}


async def main_async(args) -> int:
    cases = load_cases()
    if args.only:
        wanted = {w.strip() for w in args.only.split(",") if w.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[:args.limit]

    print(f"Running {len(cases)} cases with therapy-agent + Llama-3.2-3B.\n")

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
            state = await run_agent(
                gene=inp["gene"],
                mutation=inp["mutation"],
                disease_phenotype=inp["disease_phenotype"],
            )
            elapsed = time.time() - t0
            strat = state.get("strategy") or {}
            mech = state.get("molecular_mechanism")
            pred = strat.get("target_protein") or ""
            sc = score(pred, exp)
            mod_pred = strat.get("modulation_type", "")
            conf = float(strat.get("confidence_score", 0.0) or 0.0)

            flag = "OK " if sc["recovered"] else "MISS"
            print(f"    -> {flag}  pred={pred!r}  expected={exp['target_protein']}")
            print(f"       mechanism={mech}  modulation={mod_pred}  conf={conf:.2f}  ({elapsed:.1f}s)")
            results.append({
                "case_id": cid,
                "gene": inp["gene"],
                "expected_target": exp["target_protein"],
                "expected_aliases": exp.get("target_aliases", []),
                "expected_mechanism": exp.get("mechanism_class"),
                "predicted_target": pred,
                "predicted_modulation": mod_pred,
                "predicted_mechanism": mech,
                "predicted_confidence": conf,
                "recovered": sc["recovered"],
                "matched_via": sc["matched_via"],
                "rationale": strat.get("rationale", ""),
                "elapsed_s": round(elapsed, 1),
            })
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"    -> ERROR {exc} ({elapsed:.1f}s)")
            results.append({
                "case_id": cid,
                "gene": inp["gene"],
                "expected_target": exp["target_protein"],
                "predicted_target": "",
                "recovered": False,
                "error": str(exc),
                "elapsed_s": round(elapsed, 1),
            })
        print()

    total = time.time() - t_start
    recovered = sum(1 for r in results if r.get("recovered"))
    print(f"=== {recovered}/{len(results)} recovered ({total:.0f}s total) ===\n")

    if args.out:
        Path(args.out).write_text(
            json.dumps({
                "backend": os.environ.get("THERAPY_AGENT_LLM_BACKEND", "anthropic"),
                "model_path": os.environ.get("LLAMA_MODEL_PATH", ""),
                "n_cases": len(results),
                "recovered": recovered,
                "total_seconds": round(total, 1),
                "results": results,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {args.out}")
    return 0 if recovered == len(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=str, default="",
                    help="Comma-separated case IDs to run.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap the number of cases run.")
    ap.add_argument("--out", type=Path, default=Path("blinded_results.json"))
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
