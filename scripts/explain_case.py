#!/usr/bin/env python3
"""Per-case explainer: given a result JSON + case_id, render the agent's
decision chain in plain prose.

Reads:
  - case_id from the user
  - the result JSON containing that case
  - the YAML benchmark case (for inputs + expected outputs)

Writes a markdown explanation:
  - what was asked (inputs)
  - what the agent picked (target + modality + rationale)
  - what the expected answer was (target + aliases + valid_targets)
  - whether it matched, and via which mechanism
  - the reasoning trace (Stage 1 pattern, Stage 2 votes, critique)
  - the failure mode if missed

This is the "tell me what happened on case X" tool. Faster than reading
the full JSON; gives a reviewer a one-page summary per case.

Usage:
    python scripts/explain_case.py sandbox/blinded_v20_val_llama.json crinecerfont_cah
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml  # type: ignore[import]


_AGENT = Path(__file__).resolve().parents[1].parent / "therapy-agent"
_BM = _AGENT / "benchmarks"


def _find_yaml(case_id: str) -> Path | None:
    for p in _BM.rglob("*.yaml"):
        if p.stem == case_id or p.stem.endswith(case_id):
            return p
    return None


def _explain(run: dict, case: dict, case_id: str, yaml_path: Path | None) -> str:
    lines: list[str] = []
    lines.append(f"# Case explanation: {case_id}\n")

    # Source.
    lines.append(f"Run: `{run.get('model_path') or run.get('backend')}`")
    lines.append(f"Cases in run: {run.get('n_cases')}")
    lines.append("")

    # Inputs.
    if yaml_path:
        ydoc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        inp = ydoc.get("input", {})
        lines.append("## Inputs (what the agent saw)\n")
        lines.append(f"- gene: `{inp.get('gene')}`")
        lines.append(f"- mutation: `{inp.get('mutation')}`")
        lines.append(f"- disease_phenotype: `{inp.get('disease_phenotype')[:200]}`")
        lines.append("")
    else:
        lines.append("## Inputs (case YAML not found locally)\n")

    # Expected.
    lines.append("## Expected (what curators say is the right answer)\n")
    lines.append(f"- expected_target: `{case.get('expected_target')}`")
    if case.get("expected_aliases"):
        ali = case["expected_aliases"][:6]
        lines.append(f"- expected_aliases: {', '.join(f'`{a}`' for a in ali)}")
    lines.append(f"- expected_modulation: `{case.get('expected_modulation')}`")
    if case.get("expected_min_confidence") is not None:
        lines.append(f"- expected_min_confidence: {case['expected_min_confidence']}")
    lines.append("")

    # Predicted.
    lines.append("## Predicted (what the agent said)\n")
    lines.append(f"- predicted_target: `{case.get('predicted_target')}`")
    lines.append(f"- predicted_modulation: `{case.get('predicted_modulation')}`")
    lines.append(f"- predicted_mechanism: `{case.get('predicted_mechanism')}`")
    conf = case.get("predicted_confidence")
    if isinstance(conf, (int, float)):
        lines.append(f"- predicted_confidence: {conf:.2f}")
    lines.append(f"- strategy_pattern_id: `{case.get('strategy_pattern_id', '')}`")
    lines.append(f"- strategy_target_kind: `{case.get('strategy_target_kind', '')}`")
    lines.append("")
    rat = case.get("predicted_rationale", "")
    if rat:
        lines.append("### Predicted rationale\n")
        lines.append(f"> {rat}")
        lines.append("")

    # Verdict.
    lines.append("## Verdict\n")
    if case.get("target_recovered"):
        lines.append(f"- ✓ target recovered (via `{case.get('target_matched_via')}` "
                     f"as kind `{case.get('target_matched_via_kind')}`)")
    else:
        lines.append("- ✗ target MISSED")
        if case.get("predicted_target") and case.get("gene"):
            if (case["predicted_target"].split()[0].upper() ==
                    case["gene"].upper()):
                lines.append("  - failure mode: **disease_gene_default**")
    if case.get("modality_recovered"):
        lines.append("- ✓ modality also correct")
    else:
        lines.append("- ✗ modality miss")
    lines.append("")

    # Reasoning trace.
    trace = case.get("reasoning_trace") or []
    if trace:
        lines.append("## Reasoning trace (first 6 lines)\n")
        for t in trace:
            lines.append(f"- {t}")
        lines.append("")

    # Token / latency.
    lines.append("## Cost\n")
    lines.append(f"- elapsed: {case.get('elapsed_s', 0):.1f}s")
    lines.append(f"- tokens: in={case.get('tokens_in_total')}, "
                 f"out={case.get('tokens_out_total')}")
    per_node = case.get("llm_calls_per_node") or {}
    if per_node:
        nodes = ", ".join(f"{k}:{v}" for k, v in per_node.items())
        lines.append(f"- LLM calls per node: {nodes}")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json", type=Path)
    ap.add_argument("case_id", type=str)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    run = json.loads(args.result_json.read_text(encoding="utf-8"))
    results = run.get("results", [])
    case = next((r for r in results if r.get("case_id") == args.case_id), None)
    if not case:
        print(f"Case `{args.case_id}` not found in {args.result_json.name}")
        print(f"Available case_ids: "
              f"{', '.join(r.get('case_id', '?') for r in results)}")
        return 1
    yaml_path = _find_yaml(args.case_id)
    print(_explain(run, case, args.case_id, yaml_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
