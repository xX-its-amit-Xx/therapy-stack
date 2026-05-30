#!/usr/bin/env python3
"""Side-by-side diff of two benchmark runs.

Compare a "baseline" and a "candidate" results JSON, case-by-case. Highlights:
  - cases that REGRESSED (was OK, now MISS) -- the things a PR breaks
  - cases that RECOVERED (was MISS, now OK) -- the things a PR fixes
  - cases that CHANGED prediction but stayed correct/incorrect -- "soft" changes

Output is markdown suitable for posting as a PR comment. The intended use
is in CI: after every prompt or pipeline change, diff against the locked
baseline run and surface the per-case deltas as a comment on the PR.

Usage:
    python scripts/run_diff.py \\
        --baseline sandbox/blinded_v0.7_dev.json \\
        --candidate sandbox/blinded_v0.8_dev.json \\
        --label "v0.7 -> v0.8"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--label", type=str, default="")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    base = load(args.baseline)
    cand = load(args.candidate)

    by_id_b = {r["case_id"]: r for r in base["results"]}
    by_id_c = {r["case_id"]: r for r in cand["results"]}

    common = sorted(set(by_id_b) & set(by_id_c))
    only_base = sorted(set(by_id_b) - set(by_id_c))
    only_cand = sorted(set(by_id_c) - set(by_id_b))

    regressed: list[tuple[str, str, str]] = []
    recovered: list[tuple[str, str, str]] = []
    soft_change: list[tuple[str, bool, str, str]] = []
    unchanged_ok: list[str] = []
    unchanged_miss: list[str] = []

    for cid in common:
        b = by_id_b[cid]
        c = by_id_c[cid]
        b_ok = bool(b.get("target_recovered"))
        c_ok = bool(c.get("target_recovered"))
        b_pred = b.get("predicted_target", "") or ""
        c_pred = c.get("predicted_target", "") or ""
        if b_ok and not c_ok:
            regressed.append((cid, b_pred, c_pred))
        elif (not b_ok) and c_ok:
            recovered.append((cid, b_pred, c_pred))
        elif b_pred != c_pred:
            soft_change.append((cid, b_ok, b_pred, c_pred))
        elif b_ok:
            unchanged_ok.append(cid)
        else:
            unchanged_miss.append(cid)

    n_b = base.get("target_recovered", 0)
    n_c = cand.get("target_recovered", 0)
    n_total = cand.get("n_cases", 0) or base.get("n_cases", 0) or len(common)

    delta = n_c - n_b
    sign = "+" if delta >= 0 else ""
    label_part = f" -- {args.label}" if args.label else ""

    lines = [
        f"# Run diff{label_part}",
        "",
        f"- **Baseline:** `{args.baseline.name}` -- {n_b}/{n_total}",
        f"- **Candidate:** `{args.candidate.name}` -- {n_c}/{n_total}",
        f"- **Delta:** {sign}{delta}",
        "",
    ]

    if regressed:
        lines.append("## REGRESSED (was OK, now MISS)")
        lines.append("")
        lines.append("| Case | Baseline pred | Candidate pred |")
        lines.append("|---|---|---|")
        for cid, bp, cp in regressed:
            lines.append(f"| `{cid}` | `{bp}` | `{cp}` |")
        lines.append("")
    if recovered:
        lines.append("## RECOVERED (was MISS, now OK)")
        lines.append("")
        lines.append("| Case | Baseline pred | Candidate pred |")
        lines.append("|---|---|---|")
        for cid, bp, cp in recovered:
            lines.append(f"| `{cid}` | `{bp}` | `{cp}` |")
        lines.append("")
    if soft_change:
        lines.append("## SOFT CHANGE (prediction changed, scoring unchanged)")
        lines.append("")
        lines.append("| Case | Status | Baseline pred | Candidate pred |")
        lines.append("|---|---|---|---|")
        for cid, ok, bp, cp in soft_change:
            status = "OK" if ok else "MISS"
            lines.append(f"| `{cid}` | {status} | `{bp}` | `{cp}` |")
        lines.append("")
    if only_base:
        lines.append(f"## Cases present only in baseline ({len(only_base)})")
        lines.append("")
        for cid in only_base:
            lines.append(f"- `{cid}`")
        lines.append("")
    if only_cand:
        lines.append(f"## Cases present only in candidate ({len(only_cand)})")
        lines.append("")
        for cid in only_cand:
            lines.append(f"- `{cid}`")
        lines.append("")

    if not (regressed or recovered or soft_change or only_base or only_cand):
        lines.append("No differences. Predictions identical case-by-case.")

    # Headline summary line for CI integration.
    summary = (
        f"DIFF: {sign}{delta} cases | "
        f"regressed={len(regressed)} recovered={len(recovered)} "
        f"soft_change={len(soft_change)} unchanged_ok={len(unchanged_ok)} "
        f"unchanged_miss={len(unchanged_miss)}"
    )
    lines.insert(0, "")
    lines.insert(0, summary)
    print("\n".join(lines))

    # Exit code: nonzero if regressions found (for CI gating).
    return 1 if regressed else 0


if __name__ == "__main__":
    raise SystemExit(main())
