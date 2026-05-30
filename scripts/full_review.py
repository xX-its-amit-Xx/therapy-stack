#!/usr/bin/env python3
"""Full-review report: one command that produces a complete review
package from a result JSON.

For each blinded_*.json, generates:
  - markdown summary (target/modality/citation recovery, Wilson CI,
    disease-gene-default rate)
  - miss taxonomy
  - pattern distribution (if strategy_pattern_id present)
  - calibration headline numbers (ECE, Brier)
  - node contribution (cost economy)
  - links to the HTML evidence report (regenerated)

The output is a single markdown file (default: <input>.review.md) and
a sibling .html evidence file.

This is the "give me everything you've got on this run" tool. Useful
for sharing a single artifact with a reviewer rather than 8 separate
script outputs.

Usage:
    python scripts/full_review.py sandbox/blinded_v20_val_llama.json
    python scripts/full_review.py sandbox/blinded_v20_val_llama.json \
        --out sandbox/REVIEW_v20_val.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _run_script(name: str, *extra: str) -> str:
    """Run scripts/{name} and capture stdout as a string."""
    py = sys.executable
    cmd = [py, str(_ROOT / "scripts" / name)] + list(extra)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", check=False)
        return r.stdout or "(no output)"
    except Exception as e:
        return f"(script {name} failed: {e})"


def _summary(d: dict) -> str:
    n = d.get("n_cases", 0)
    target = d.get("target_recovered", 0)
    modality = d.get("modality_recovered", 0)
    citation = d.get("citation_recovered", 0)
    full = d.get("full_recovered", 0)
    wilson = d.get("wilson_ci_target", [0, 0])
    dg_rate = d.get("disease_gene_default_rate")
    backend = d.get("backend", "?")
    wall = d.get("total_seconds", 0)
    s = f"""
- Backend: `{backend}`
- N cases: {n}
- Target recovered: {target}/{n} ({target/max(n,1)*100:.0f}%) -- Wilson 95% CI [{wilson[0]*100:.0f}%, {wilson[1]*100:.0f}%]
- Modality recovered: {modality}/{n}
- Citation recovered: {citation}/{n}
- Full (target+modality+citation): {full}/{n}
- Baseline disease-gene: {d.get('baseline_disease_gene_recovered', 0)}/{n}
- Baseline 1st interactor: {d.get('baseline_first_interactor_recovered', 0)}/{n}
- Total wall: {wall:.1f}s ({wall/60:.1f} min)
"""
    if dg_rate is not None:
        s += f"- Disease-gene-default rate (cases where expected != disease gene): {dg_rate*100:.0f}%\n"
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if not args.result_json.exists():
        print(f"FAIL: {args.result_json} not found")
        return 1
    out_md = args.out or args.result_json.with_suffix(".review.md")
    out_html = args.result_json.with_suffix(".html")

    d = json.loads(args.result_json.read_text(encoding="utf-8"))

    sections: list[str] = []
    sections.append(f"# Full review -- {args.result_json.name}\n")
    sections.append("## Headline")
    sections.append(_summary(d))

    sections.append("## Miss taxonomy")
    sections.append(_run_script("miss_taxonomy.py", str(args.result_json)))

    if any(r.get("strategy_pattern_id") for r in d.get("results", [])):
        sections.append("## Pattern distribution")
        sections.append(_run_script("pattern_distribution.py",
                                     str(args.result_json)))

    sections.append("## Node contribution + token economy")
    sections.append(_run_script("node_contribution.py",
                                 str(args.result_json)))

    sections.append("## Calibration")
    sections.append(_run_script("calibration.py", str(args.result_json)))

    # HTML evidence report.
    sections.append("## Per-case evidence (HTML)")
    _run_script("evidence_report.py", str(args.result_json),
                 "--out", str(out_html))
    rel_html = out_html.name
    sections.append(f"Per-case evidence: [{rel_html}](./{rel_html})\n")

    md = "\n".join(sections)
    out_md.write_text(md, encoding="utf-8")
    print(f"Wrote review markdown: {out_md} ({len(md)} chars)")
    print(f"Wrote evidence HTML:   {out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
