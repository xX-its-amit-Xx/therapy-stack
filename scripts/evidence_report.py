#!/usr/bin/env python3
"""Per-case HTML evidence-trace report.

Reads a blinded_*.json result file and emits a static HTML page with
one card per case showing:
  - inputs (gene, mutation, disease)
  - expected target / aliases / valid_targets
  - predicted target / modality / rationale
  - target_recovered status with which alias matched
  - per-node LLM call count + tokens + elapsed
  - confidence_meets_min and self-consistency votes if available

This is the artifact that lets a reviewer answer "is the agent right
for the right reason?" without reading the JSON.

Usage:
    python scripts/evidence_report.py sandbox/blinded_v20_val_llama.json \
        --out sandbox/report_v20_val.html

The output is a self-contained HTML file (no external assets).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       Roboto, "Helvetica Neue", sans-serif; max-width: 1100px;
       margin: 2em auto; padding: 0 1em; color: #1a1a1a; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }
h2 { margin-top: 1.5em; }
.summary { background: #f4f6f8; padding: 1em; border-radius: 6px;
           border: 1px solid #ddd; }
.summary table { border-collapse: collapse; }
.summary td { padding: 0.2em 0.6em; }
.case { border: 1px solid #ddd; border-radius: 6px; padding: 1em;
        margin-bottom: 1em; background: #fff; }
.case.hit { border-left: 6px solid #2e7d32; }
.case.miss { border-left: 6px solid #c62828; }
.case h3 { margin: 0 0 0.4em 0; font-size: 1.05em; }
.case .pred { background: #f9fbfd; padding: 0.6em 0.8em;
              border-left: 3px solid #1565c0; margin: 0.5em 0; }
.case .exp { background: #faf4f4; padding: 0.6em 0.8em;
             border-left: 3px solid #c62828; margin: 0.5em 0; }
.case .rat { color: #444; font-style: italic; padding: 0.4em 0;
             border-top: 1px dashed #ddd; margin-top: 0.5em; }
.case .meta { color: #666; font-size: 0.85em; margin-top: 0.6em; }
.tag { display: inline-block; padding: 0.1em 0.5em; border-radius: 4px;
       font-size: 0.8em; margin-right: 0.4em; }
.tag.hit { background: #c8e6c9; color: #1b5e20; }
.tag.miss { background: #ffcdd2; color: #b71c1c; }
.tag.info { background: #e3f2fd; color: #0d47a1; }
.kv { display: grid; grid-template-columns: 140px 1fr; gap: 0.2em 0.8em; }
.kv dt { color: #555; font-weight: 600; }
"""


def _tag(label: str, kind: str) -> str:
    return f'<span class="tag {kind}">{html.escape(label)}</span>'


def _render_case(c: dict) -> str:
    hit = bool(c.get("target_recovered"))
    cls = "hit" if hit else "miss"
    case_id = html.escape(c.get("case_id", "?"))
    gene = html.escape(c.get("gene", ""))
    exp_target = html.escape(c.get("expected_target", ""))
    pred_target = html.escape(str(c.get("predicted_target") or "Unknown"))
    pred_mod = html.escape(str(c.get("predicted_modulation") or ""))
    pred_mech = html.escape(str(c.get("predicted_mechanism") or ""))
    pred_conf = c.get("predicted_confidence")
    pred_conf_s = f"{pred_conf:.2f}" if isinstance(pred_conf, (int, float)) else "?"
    pred_rat = html.escape(str(c.get("predicted_rationale") or ""))
    matched_via = html.escape(str(c.get("target_matched_via") or ""))
    matched_kind = html.escape(str(c.get("target_matched_via_kind") or ""))
    aliases = c.get("expected_aliases") or []
    elapsed = c.get("elapsed_s") or 0.0
    tin = c.get("tokens_in_total") or 0
    tout = c.get("tokens_out_total") or 0
    per_node = c.get("llm_calls_per_node") or {}
    per_node_s = ", ".join(f"{k}:{v}" for k, v in per_node.items()) or "n/a"
    sc_votes = c.get("self_consistency_votes")
    sc_s = ""
    if sc_votes:
        sc_s = (f"<div class='meta'>self-consistency: "
                f"{html.escape(str(sc_votes))}</div>")
    conf_meets = c.get("confidence_meets_min")
    conf_tag = (_tag("conf>=min", "hit") if conf_meets
                else _tag("conf<min", "miss"))

    target_tag = _tag("target recovered", "hit") if hit else _tag("target missed", "miss")
    mod_tag = (_tag("modality OK", "hit") if c.get("modality_recovered")
               else _tag("modality miss", "miss"))
    cite_tag = (_tag("cite OK", "hit") if c.get("citation_recovered")
                else _tag("cite miss", "info"))

    return f"""
<div class='case {cls}'>
  <h3>{case_id} &middot; gene={gene} &middot; target_exp={exp_target}</h3>
  {target_tag}{mod_tag}{cite_tag}{conf_tag}
  <div class='pred'>
    <strong>Predicted:</strong> {pred_target}
    &middot; modulation={pred_mod}
    &middot; mechanism={pred_mech}
    &middot; conf={pred_conf_s}
  </div>
  <div class='exp'>
    <strong>Expected:</strong> {exp_target}
    &middot; aliases=[{", ".join(html.escape(str(a)) for a in aliases[:6])}{"..." if len(aliases) > 6 else ""}]
    &middot; matched_via={matched_via} ({matched_kind})
  </div>
  <div class='rat'>{pred_rat}</div>
  {sc_s}
  <div class='meta'>elapsed={elapsed:.1f}s &middot; tokens in/out={tin}/{tout} &middot; LLM calls={per_node_s}</div>
</div>
"""


def _render(doc: dict, source_name: str) -> str:
    results = doc.get("results", [])
    n = doc.get("n_cases", len(results))
    hits = doc.get("target_recovered") or sum(
        1 for r in results if r.get("target_recovered"))
    mod_hits = doc.get("modality_recovered") or 0
    cite_hits = doc.get("citation_recovered") or 0
    wall = doc.get("total_seconds", 0)
    ci = doc.get("wilson_ci_target") or [0.0, 0.0]
    backend = doc.get("backend", "?")
    model = doc.get("model_path", "")

    summary = f"""
<div class='summary'>
  <table>
    <tr><td>source</td><td><code>{html.escape(source_name)}</code></td></tr>
    <tr><td>backend</td><td>{html.escape(backend)}</td></tr>
    <tr><td>model</td><td><code>{html.escape(model)}</code></td></tr>
    <tr><td>cases</td><td>{n}</td></tr>
    <tr><td>target recovered</td><td>{hits}/{n} ({hits/max(n,1)*100:.0f}%)
            -- Wilson 95% CI [{ci[0]*100:.0f}%, {ci[1]*100:.0f}%]</td></tr>
    <tr><td>modality recovered</td><td>{mod_hits}/{n}</td></tr>
    <tr><td>citation recovered</td><td>{cite_hits}/{n}</td></tr>
    <tr><td>total wall</td><td>{wall:.1f}s ({wall/60:.1f} min)</td></tr>
  </table>
</div>
"""
    cards = "\n".join(_render_case(c) for c in results)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>therapy-stack evidence: {html.escape(source_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>therapy-stack evidence trace</h1>
<p>One card per blinded case. Green-left = target recovered;
red-left = target missed. Look at the rationale to judge whether
the agent picked the right target for the right reason -- or got
lucky with a disease-gene-default heuristic that happened to match.</p>
{summary}
<h2>Per-case evidence (N = {len(results)})</h2>
{cards}
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="output HTML path (default: <input>.html)")
    args = ap.parse_args()

    src = args.input
    out = args.out or src.with_suffix(".html")

    doc = json.loads(src.read_text(encoding="utf-8"))
    html_str = _render(doc, src.name)
    out.write_text(html_str, encoding="utf-8")
    print(f"wrote {out} ({len(html_str)} chars, {len(doc.get('results', []))} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
