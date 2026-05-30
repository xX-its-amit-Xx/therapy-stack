#!/usr/bin/env python3
"""LLM-as-judge for rationale plausibility.

Reads a blinded_*.json and asks a judge LLM, for each case:
"Given the disease (gene + phenotype) and the agent's stated rationale,
is the proposed target a biologically plausible therapeutic strategy?
Score 0-3:
  0 -- contradicts known biology
  1 -- biologically irrelevant (off-pathway)
  2 -- biologically adjacent but not the canonical strategy
  3 -- canonical or well-validated strategy
Be strict; reward only mechanistically coherent strategies."

The plausibility score is ORTHOGONAL to target_recovery. A 3 on
plausibility with target_recovered=False means the agent picked a
defensible alternative target that the YAML doesn't list. A 2/3 on
target_recovered=True means the curator-chosen target was reached but
the rationale doesn't justify it well. Both are useful diagnostic
signals.

Cost: ~$0.005 per case on GPT-4o-mini, or free on local Llama.

Usage:
    OPENAI_API_KEY=sk-... \\
    python scripts/rationale_judge.py \\
        sandbox/blinded_v20_val_llama.json \\
        --judge-model gpt-4o-mini
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


_SYSTEM = """You are a biology-expert judge evaluating drug-discovery rationales.

You will see a disease (gene + phenotype) and the agent's proposed target
plus its rationale for that proposal. Score the rationale's biological
plausibility on a 0-3 scale:

  0 -- rationale CONTRADICTS known biology. The proposed target would
       not, mechanistically, alter the disease in the predicted direction.
  1 -- rationale is biologically IRRELEVANT. The proposed target is in
       a different pathway / cell type / process; no plausible therapeutic
       link to the disease phenotype.
  2 -- rationale is biologically ADJACENT but NOT the canonical
       therapeutic strategy. The target is in the right pathway / family
       but a different node would be more direct or well-precedented.
  3 -- rationale describes a CANONICAL or well-validated therapeutic
       strategy. The mechanism described is consistent with the known
       biology and would plausibly resolve / mitigate the disease.

Be strict. Only score 3 if the mechanism is coherent end-to-end. Score
1 if the agent has clearly hallucinated a relationship.

Return strict JSON, NO markdown:
{
  "plausibility": 0 | 1 | 2 | 3,
  "reasoning": "<one sentence explaining the score>"
}
"""


_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _parse(text: str) -> dict | None:
    candidates = [text.strip()]
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    m = _JSON_RE.search(text)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", type=Path,
                    help="blinded_*.json result file to judge")
    ap.add_argument("--judge-model", type=str, default="gpt-4o-mini",
                    help="OpenAI model name (default gpt-4o-mini)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Path to write per-case judgments JSON. "
                         "Defaults to <input>_judged.json")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY required for rationale judge.",
              file=sys.stderr)
        return 2

    import openai
    client = openai.OpenAI()

    d = json.loads(args.results.read_text(encoding="utf-8"))
    results = d.get("results") or []
    if not results:
        print("No results to judge", file=sys.stderr); return 1

    judged: list[dict] = []
    score_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for r in results:
        prompt = (
            f"Disease gene: {r['gene']}\n"
            f"Disease phenotype: (see expected case context)\n"
            f"Agent's proposed target: {r.get('predicted_target') or '(none)'}\n"
            f"Agent's proposed modality: {r.get('predicted_modulation') or '?'}\n"
            f"Agent's rationale:\n"
            f"{(r.get('predicted_rationale') or '(no rationale)')[:1500]}\n\n"
            f"Score the rationale's biological plausibility (0-3). Return JSON only."
        )
        try:
            resp = client.chat.completions.create(
                model=args.judge_model,
                max_tokens=200,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.choices[0].message.content or ""
            data = _parse(text) or {}
            score = int(data.get("plausibility", -1))
            if score not in (0, 1, 2, 3):
                score = -1
            reasoning = (data.get("reasoning") or "").strip()
        except Exception as e:
            score = -1
            reasoning = f"judge error: {e}"

        if score in score_counts:
            score_counts[score] += 1
        judged.append({
            "case_id": r["case_id"],
            "target_recovered": bool(r.get("target_recovered")),
            "predicted_target": r.get("predicted_target"),
            "plausibility": score,
            "judge_reasoning": reasoning,
        })

    n = len(judged)
    mean = sum((j["plausibility"] for j in judged if j["plausibility"] >= 0)) / max(1, sum(1 for j in judged if j["plausibility"] >= 0))
    print(f"# Rationale plausibility -- {args.results.name}")
    print(f"\n**Judge model:** `{args.judge_model}`  |  **N cases judged:** {n}")
    print(f"**Mean plausibility (0-3):** {mean:.2f}")
    print(f"**Score distribution:** "
          f"0={score_counts[0]} | 1={score_counts[1]} | "
          f"2={score_counts[2]} | 3={score_counts[3]}\n")
    print("| Case | Target | Recovered? | Plausibility | Judge reasoning |")
    print("|---|---|---|---|---|")
    for j in judged:
        rec = "Y" if j["target_recovered"] else "N"
        plaus = j["plausibility"] if j["plausibility"] >= 0 else "ERR"
        rsn = (j["judge_reasoning"] or "").replace("|", "/")
        print(f"| `{j['case_id']}` | `{j['predicted_target']}` | {rec} | {plaus} | {rsn[:120]} |")

    out_path = args.out or args.results.with_name(args.results.stem + "_judged.json")
    out_path.write_text(json.dumps({
        "judge_model": args.judge_model,
        "input": str(args.results),
        "n_cases": n,
        "mean_plausibility": round(mean, 2),
        "score_distribution": score_counts,
        "judged": judged,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
