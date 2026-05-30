#!/usr/bin/env python3
"""Calibration analysis: does the agent's self-reported confidence track
its actual accuracy?

Reads any blinded_*.json result file and bins predictions by predicted
confidence. For each bin, reports: count, fraction recovered, and the
"calibration gap" (predicted - actual). A well-calibrated model has
gaps near 0; an over-confident model has positive gaps (claims 0.9
confidence, recovers 0.6).

Usage:
    python scripts/calibration.py sandbox/blinded_v20_val_llama.json
    python scripts/calibration.py sandbox/*.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from collections import defaultdict


_BINS = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.01)]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bin_for(conf: float) -> tuple[float, float] | None:
    for lo, hi in _BINS:
        if lo <= conf < hi:
            return (lo, hi)
    return None


def brier_score(results: list[dict]) -> float:
    """Mean squared error between predicted confidence and binary outcome."""
    items = [(float(r.get("predicted_confidence") or 0.0),
              1.0 if r.get("target_recovered") else 0.0)
             for r in results]
    if not items:
        return float("nan")
    return sum((p - o) ** 2 for p, o in items) / len(items)


def expected_calibration_error(results: list[dict], n_bins: int = 5) -> float:
    """ECE: weighted average |predicted - actual| across confidence bins."""
    bins: dict[tuple[float, float], list[tuple[float, int]]] = defaultdict(list)
    for r in results:
        c = float(r.get("predicted_confidence") or 0.0)
        b = bin_for(c)
        if b is None:
            continue
        bins[b].append((c, 1 if r.get("target_recovered") else 0))
    total = sum(len(v) for v in bins.values())
    if total == 0:
        return float("nan")
    ece = 0.0
    for bin_range, items in bins.items():
        if not items:
            continue
        avg_conf = sum(c for c, _ in items) / len(items)
        avg_acc = sum(o for _, o in items) / len(items)
        ece += (len(items) / total) * abs(avg_conf - avg_acc)
    return ece


def render_table(results: list[dict], label: str) -> str:
    lines = [f"## Calibration -- {label}", ""]
    lines.append("| Conf bin | N | Mean conf | Mean accuracy | Gap (conf - acc) |")
    lines.append("|---|---|---|---|---|")
    bins: dict[tuple[float, float], list[tuple[float, int]]] = defaultdict(list)
    for r in results:
        c = float(r.get("predicted_confidence") or 0.0)
        b = bin_for(c)
        if b is None:
            continue
        bins[b].append((c, 1 if r.get("target_recovered") else 0))
    for lo, hi in _BINS:
        items = bins.get((lo, hi), [])
        n = len(items)
        if n == 0:
            lines.append(f"| [{lo:.2f}, {hi:.2f}) | 0 | -- | -- | -- |")
            continue
        avg_conf = sum(c for c, _ in items) / n
        avg_acc = sum(o for _, o in items) / n
        gap = avg_conf - avg_acc
        sign = "+" if gap >= 0 else ""
        lines.append(
            f"| [{lo:.2f}, {hi:.2f}) | {n} | {avg_conf:.2f} | {avg_acc:.2f} | {sign}{gap:.2f} |"
        )
    ece = expected_calibration_error(results)
    brier = brier_score(results)
    lines.append("")
    lines.append(f"**ECE (lower = better):** {ece:.3f}")
    lines.append(f"**Brier score (lower = better):** {brier:.3f}")
    if ece > 0.2:
        lines.append("")
        lines.append("> Calibration is poor. The model's confidence is meaningfully decoupled "
                     "from its accuracy; downstream consumers should NOT use confidence as a "
                     "trustworthy reliability signal.")
    elif ece > 0.1:
        lines.append("")
        lines.append("> Calibration is mediocre -- usable as a directional signal but not as "
                     "a reliability gate.")
    else:
        lines.append("")
        lines.append("> Calibration is reasonable. Confidence can be used as a soft "
                     "reliability gate (e.g., flag low-confidence outputs for human review).")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path,
                    help="One or more blinded_*.json result files")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    for p in args.paths:
        if not p.exists():
            print(f"SKIP {p}: not found")
            continue
        try:
            d = load(p)
        except Exception as e:
            print(f"SKIP {p}: parse failed ({e})")
            continue
        results = d.get("results") or []
        if not results:
            print(f"SKIP {p}: no results")
            continue
        label = f"{p.name} (backend={d.get('backend', '?')}, n={len(results)})"
        print(render_table(results, label))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
