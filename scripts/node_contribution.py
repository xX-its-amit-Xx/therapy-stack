#!/usr/bin/env python3
"""Per-node marginal-value report from a benchmark run.

The therapy-agent LangGraph has 9 nodes. After a run, each result
JSON has `llm_calls_per_node` showing how many LLM calls each node
made for that case. This script aggregates:

  - total LLM calls per node across the run
  - what fraction of cases the node fired on
  - whether the node fires more on HITS than MISSES (suggestive of
    being load-bearing) or vice versa (suggestive of being a costly
    rescuer that runs after a problem)

This is the input for "should we keep this node?" conversations.
A node that fires equally on hits and misses is doing the same work
regardless of outcome; one that disproportionately fires on misses
is consuming budget on cases that failed anyway.

Usage:
    python scripts/node_contribution.py sandbox/blinded_v20_val_llama.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    d = json.loads(args.path.read_text(encoding="utf-8"))
    results = d.get("results", [])
    n = len(results)
    if n == 0:
        print(f"{args.path.name}: no results")
        return 1
    hits = sum(1 for r in results if r.get("target_recovered"))

    # Per-node aggregation.
    calls_total = Counter()
    calls_on_hits = Counter()
    calls_on_misses = Counter()
    cases_with_node = Counter()
    for r in results:
        per_node = r.get("llm_calls_per_node") or {}
        recovered = bool(r.get("target_recovered"))
        for node, count in per_node.items():
            calls_total[node] += count
            cases_with_node[node] += 1
            if recovered:
                calls_on_hits[node] += count
            else:
                calls_on_misses[node] += count

    # Total tokens by hit/miss bucket -- for cost analysis of failures.
    tok_in_hit = sum(r.get("tokens_in_total", 0) for r in results
                     if r.get("target_recovered"))
    tok_in_miss = sum(r.get("tokens_in_total", 0) for r in results
                      if not r.get("target_recovered"))
    tok_out_hit = sum(r.get("tokens_out_total", 0) for r in results
                      if r.get("target_recovered"))
    tok_out_miss = sum(r.get("tokens_out_total", 0) for r in results
                       if not r.get("target_recovered"))

    print(f"# Node contribution -- {args.path.name}")
    print(f"\nCases: {n} total ({hits} recovered, {n - hits} missed)")
    print()
    print("## LLM calls per node")
    print()
    print("| Node | Cases firing | Total calls | Calls on hits | Calls on misses | Avg/case |")
    print("|---|---|---|---|---|---|")
    for node in sorted(calls_total, key=lambda k: -calls_total[k]):
        cw = cases_with_node[node]
        ct = calls_total[node]
        ch = calls_on_hits[node]
        cm = calls_on_misses[node]
        print(f"| `{node}` | {cw}/{n} ({cw/n*100:.0f}%) | {ct} | {ch} | {cm} | {ct/max(cw,1):.1f} |")

    print()
    print("## Token economy of failures")
    print()
    print(f"- Tokens consumed on hits ({hits} cases):   in={tok_in_hit}, out={tok_out_hit}")
    print(f"- Tokens consumed on misses ({n-hits} cases): in={tok_in_miss}, out={tok_out_miss}")
    if hits and n - hits:
        in_per_hit = tok_in_hit / hits
        in_per_miss = tok_in_miss / (n - hits)
        out_per_hit = tok_out_hit / hits
        out_per_miss = tok_out_miss / (n - hits)
        print(f"- Per-case in tokens: hits={in_per_hit:.0f}, misses={in_per_miss:.0f} "
              f"(misses spend {in_per_miss/max(in_per_hit,1):.2f}x the input)")
        print(f"- Per-case out tokens: hits={out_per_hit:.0f}, misses={out_per_miss:.0f}")
        print()
        if in_per_miss > 1.3 * in_per_hit:
            print("> Misses are consuming significantly more tokens than hits. "
                  "Look at which nodes fire on miss cases -- the pipeline is "
                  "spinning on failures rather than failing fast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
