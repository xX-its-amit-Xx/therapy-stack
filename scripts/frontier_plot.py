#!/usr/bin/env python3
"""ASCII cost-vs-accuracy frontier across benchmark runs.

Reads any number of blinded_*.json files and produces an ASCII scatter
plot of accuracy vs cost (or wall time). Cost is estimated from
tokens_in_total / tokens_out_total when the backend is OpenAI, or
listed as "local" for llama-cpp runs.

The Pareto frontier (configurations that are not dominated by any
other on both accuracy AND cost) is marked with '*' and listed
explicitly. Configurations dominated on both axes are not on the
frontier and may be safely deprioritized.

Usage:
    python scripts/frontier_plot.py sandbox/blinded_*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# OpenAI gpt-4o pricing (Dec 2024): $2.50/M in, $10.00/M out.
# gpt-4o-mini: $0.15/M in, $0.60/M out.
_PRICING = {
    "gpt-4o":        (2.50, 10.00),
    "gpt-4o-mini":   (0.15, 0.60),
    "gpt-4-turbo":   (10.00, 30.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}


def estimate_cost(d: dict) -> float | None:
    """Return USD cost estimate for a run, or None if local."""
    backend = d.get("backend", "?")
    if backend != "openai":
        return None
    model = d.get("model_path") or ""  # field name from run_blinded
    # Better: scan per-case for OPENAI_MODEL via env -- not stored. Use total tokens.
    tot_in = sum(r.get("tokens_in_total", 0) for r in d.get("results", []))
    tot_out = sum(r.get("tokens_out_total", 0) for r in d.get("results", []))
    # Default to gpt-4o pricing if unknown.
    pin, pout = _PRICING.get("gpt-4o")
    return (tot_in / 1_000_000) * pin + (tot_out / 1_000_000) * pout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    runs: list[dict] = []
    for p in args.paths:
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        results = d.get("results") or []
        if not results:
            continue
        n = d.get("n_cases") or len(results)
        hits = sum(1 for r in results if r.get("target_recovered"))
        acc = hits / n if n else 0.0
        wall_s = d.get("total_seconds", 0)
        cost = estimate_cost(d)
        runs.append({
            "name": p.stem,
            "backend": d.get("backend", "?"),
            "acc": acc,
            "hits": hits,
            "n": n,
            "wall_min": wall_s / 60,
            "cost_usd": cost,
        })

    if not runs:
        print("No runs found")
        return 1

    # Mark Pareto frontier: not dominated on (acc, -cost-or-wall).
    # We pick wall time as the universal cost axis (local runs are
    # otherwise cost=None). Lower wall + higher acc is better.
    pareto: set[int] = set()
    for i, a in enumerate(runs):
        dominated = False
        for j, b in enumerate(runs):
            if i == j:
                continue
            if b["acc"] >= a["acc"] and b["wall_min"] <= a["wall_min"]:
                if b["acc"] > a["acc"] or b["wall_min"] < a["wall_min"]:
                    dominated = True
                    break
        if not dominated:
            pareto.add(i)

    print(f"## Cost-vs-accuracy frontier ({len(runs)} runs)\n")
    print("| Run | Backend | Acc | N | Wall (min) | Est cost | Frontier |")
    print("|---|---|---|---|---|---|---|")
    for i, r in sorted(enumerate(runs), key=lambda kv: (-kv[1]["acc"], kv[1]["wall_min"])):
        front = " * " if i in pareto else ""
        cost = f"${r['cost_usd']:.3f}" if r["cost_usd"] is not None else "local"
        print(
            f"| `{r['name']}` | {r['backend']} | "
            f"{r['acc']:.2f} ({r['hits']}/{r['n']}) | "
            f"{r['n']} | {r['wall_min']:.1f} | {cost} | {front} |"
        )

    # ASCII scatter: accuracy (0..1) vs wall (log-ish).
    # Grid 60 cols x 15 rows.
    print()
    print("Wall ->  (right = slower)")
    cols, rows = 60, 15
    max_wall = max(r["wall_min"] for r in runs) or 1.0
    grid = [[" "] * cols for _ in range(rows)]
    for i, r in enumerate(runs):
        col = min(cols - 1, int((r["wall_min"] / max_wall) * (cols - 1)))
        row = rows - 1 - min(rows - 1, int(r["acc"] * (rows - 1)))
        ch = "*" if i in pareto else "o"
        grid[row][col] = ch
    print("|" + "Acc=1.0".ljust(cols, "_") + "|")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("|" + "Acc=0.0".ljust(cols, "_") + "|")
    print()
    print("Legend: * on Pareto frontier  |  o dominated  |  scale linear in wall-min")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
