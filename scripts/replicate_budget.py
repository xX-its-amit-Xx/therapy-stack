#!/usr/bin/env python3
"""How many replicate bench runs do you need to detect a 1-case improvement?

If running the bench is non-deterministic (LLM temperature, retrieval
cache timing), each run is a sample. Comparing "9/12 -> 10/12" with one
replicate each gives a deceptive p-value because the flip rate (cases
that change predictions between replicates of the SAME config) is the
noise floor.

This calculator takes:
  - the observed flip rate (from cross_run_agreement.py)
  - the expected improvement (delta cases, e.g. +2)
  - desired alpha (default 0.05) and power (default 0.8)

And returns the minimum number of replicate runs per condition needed
to claim the improvement is significantly above the noise floor.

The math: each case is a Bernoulli trial; with paired same-pipeline
runs the case's outcome is correlated within-replicate. We approximate
the binomial proportion test for two groups.

Usage:
    python scripts/replicate_budget.py --flip-rate 0.08 --delta 2 --n 12
"""
from __future__ import annotations

import argparse
import math
import sys


def _z_for_alpha(alpha: float) -> float:
    """Approximate z-score for a one-sided alpha (from normal table)."""
    # Common values; close enough for sizing.
    table = {0.01: 2.326, 0.025: 1.960, 0.05: 1.645,
              0.1: 1.282, 0.2: 0.842}
    closest = min(table, key=lambda k: abs(k - alpha))
    return table[closest]


def replicates_needed(flip_rate: float, delta: int, n_cases: int,
                       alpha: float = 0.05, power: float = 0.8) -> int:
    """How many replicate runs per condition to detect `delta` extra hits
    with the given flip-rate noise floor at (alpha, power)?

    Approximates with the two-proportion z-test formula:
      n_per_group = ((z_alpha * sqrt(2*p_bar*q_bar) +
                       z_beta  * sqrt(p1*q1 + p2*q2))^2) / (p2 - p1)^2

    Then divides by n_cases since each run sees n_cases trials.
    """
    if delta < 1 or n_cases < 1:
        return 0
    p1 = max(0.001, flip_rate)
    p2 = p1 + (delta / n_cases)
    if p2 >= 1.0:
        return 0
    z_a = _z_for_alpha(alpha)
    z_b = _z_for_alpha(1 - power)
    p_bar = (p1 + p2) / 2
    q_bar = 1 - p_bar
    se_null = math.sqrt(2 * p_bar * q_bar)
    se_alt = math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    n_trials_per_group = ((z_a * se_null + z_b * se_alt) ** 2) / ((p2 - p1) ** 2)
    return max(1, math.ceil(n_trials_per_group / n_cases))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flip-rate", type=float, required=True,
                    help="Fraction of cases that change predictions between "
                          "replicates of the SAME config (from cross_run_agreement).")
    ap.add_argument("--delta", type=int, required=True,
                    help="Expected improvement in N cases (e.g. 2 for "
                          "'9/12 -> 11/12').")
    ap.add_argument("--n", "--n-cases", type=int, required=True,
                    dest="n_cases",
                    help="Cases per run (e.g. 12 for the val split).")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.8)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    reps = replicates_needed(args.flip_rate, args.delta, args.n_cases,
                              alpha=args.alpha, power=args.power)
    print(f"# Replicate-budget calculator")
    print()
    print(f"Inputs:")
    print(f"  flip rate (noise floor):  {args.flip_rate:.2f}")
    print(f"  improvement to detect:    +{args.delta} cases of {args.n_cases}")
    print(f"  alpha:                    {args.alpha}")
    print(f"  power:                    {args.power}")
    print()
    print(f"Recommended replicates per condition: **{reps}**")
    print()
    print(f"So a fair claim of '+{args.delta} cases' requires ~{reps} runs "
          f"on the new config AND ~{reps} runs on the baseline.")
    print()
    if reps >= 5:
        print("> The required replicate count is high. Consider either "
              "(a) expanding N (more val cases), or (b) reducing flip rate "
              "by reducing temperature / increasing self-consistency.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
