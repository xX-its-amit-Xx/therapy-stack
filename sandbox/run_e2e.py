"""
End-to-end runner: load real FDA cases -> retrieve gene context from UniProt
-> ask Llama-3.2-3B-Instruct to propose therapeutic targets -> score
against the gold molecular_target column.

Usage:
    .venv/Scripts/python.exe run_e2e.py            # all 10 cases
    .venv/Scripts/python.exe run_e2e.py --cases 5  # first N
    .venv/Scripts/python.exe run_e2e.py --only zokinvy,leqvio
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Force UTF-8 stdout on Windows so we can print PubMed Greek letters etc.
sys.stdout.reconfigure(encoding="utf-8")

from fda_strategy_triples import load_dataset

from agent import TherapyAgent, strategy_to_dict
from judge import score
from retriever import GeneContext, retrieve, parse_genes


MODEL_PATH = os.environ.get(
    "LLAMA_MODEL_PATH",
    "C:/llama-models/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
)


def build_context(genes: list[str]) -> str:
    """Retrieve UniProt context for each gene and join them."""
    blocks: list[str] = []
    for g in genes:
        try:
            ctx = retrieve(g)
        except RuntimeError as e:
            blocks.append(f"Gene symbol: {g}\nNo UniProt entry found ({e}).")
            continue
        blocks.append(ctx.as_prompt_context(max_chars=1400))
    return "\n\n---\n\n".join(blocks)


def primary_gene(genes: list[str]) -> str:
    """Pick a single primary gene to name in the prompt."""
    return genes[0] if genes else "UNKNOWN"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=10,
                    help="Run only the first N cases (default: 10).")
    ap.add_argument("--only", type=str, default="",
                    help="Comma-separated list of drug name substrings to filter to.")
    ap.add_argument("--out", type=Path, default=Path("results.json"))
    args = ap.parse_args()

    if not Path(MODEL_PATH).exists():
        print(f"ERROR: model not found at {MODEL_PATH}.", file=sys.stderr)
        return 1

    df = load_dataset()
    if args.only:
        wanted = [w.strip().lower() for w in args.only.split(",") if w.strip()]
        mask = df["drug_name_brand"].fillna("").str.lower().apply(
            lambda b: any(w in b for w in wanted)
        ) | df["drug_name_generic"].fillna("").str.lower().apply(
            lambda b: any(w in b for w in wanted)
        )
        df = df[mask]
    df = df.head(args.cases)
    print(f"Running {len(df)} cases through the pipeline.\n")

    print("Loading model:", MODEL_PATH)
    t0 = time.time()
    agent = TherapyAgent(model_path=MODEL_PATH)
    print(f"Model loaded in {time.time() - t0:.1f}s\n")

    results: list[dict] = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        case_id = row["id"]
        disease = row["indicated_disease"]
        genes = parse_genes(row["associated_genes"])
        gold_target = row["molecular_target"]
        mechanism = row["mechanism_class"]
        brand = row.get("drug_name_brand") or row.get("drug_name_generic") or "?"

        print(f"[{i}/{len(df)}] {brand}  ({mechanism})")
        print(f"    disease: {disease[:80]}")
        print(f"    genes:   {genes}")

        context = build_context(genes)
        gene_for_prompt = primary_gene(genes)

        t0 = time.time()
        strategies = agent.propose(
            disease=disease,
            gene=gene_for_prompt,
            context=context,
        )
        elapsed = time.time() - t0

        cs = score(case_id, disease, gene_for_prompt, gold_target, strategies)
        status = "OK " if cs.recovered else "MISS"
        print(f"    -> {status} rank={cs.rank_of_correct} "
              f"top_pred={cs.predicted_top_target!r} ({elapsed:.1f}s)")
        if strategies:
            for j, s in enumerate(strategies, 1):
                print(f"       {j}. {s.target}  [{s.modality}]  c={s.confidence:.2f}")
                print(f"          {s.rationale[:160]}")
        else:
            print("       (no strategies parsed)")
        print(f"    gold:     {gold_target[:120]}")
        print()

        results.append({
            "case_id": case_id,
            "brand": brand,
            "disease": disease,
            "genes": genes,
            "gold_target": gold_target,
            "mechanism_class": mechanism,
            "strategies": [strategy_to_dict(s) for s in strategies],
            "score": asdict(cs),
            "elapsed_s": round(elapsed, 2),
        })

    recovered = sum(r["score"]["recovered"] for r in results)
    ranks = [r["score"]["rank_of_correct"] for r in results if r["score"]["recovered"]]
    mean_rank = (sum(ranks) / len(ranks)) if ranks else None
    print(f"=== SUMMARY: recovered {recovered}/{len(results)}, "
          f"mean rank {mean_rank} ===")

    args.out.write_text(json.dumps({
        "model": MODEL_PATH,
        "n_cases": len(results),
        "recovered": recovered,
        "mean_rank": mean_rank,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
