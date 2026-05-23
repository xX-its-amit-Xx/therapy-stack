#!/usr/bin/env bash
# One-button end-to-end run: fetch FDA cases, run the agent on each, score
# the outputs, render the scorecard HTML.
#
# Usage: bash scripts/run_e2e.sh [--version v0.1.0]
#
# Requires ANTHROPIC_API_KEY in the environment.
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="${1:-v0.1.0}"
OUT="assets/scorecard_${VERSION}.html"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set." >&2
  exit 1
fi

python - "$OUT" <<'PY'
import sys
from pathlib import Path

from fda_strategy_triples import load_cases
from g2p_rag import Retriever
from therapy_agent import TherapyAgent
from bio_rag_eval import score_case, render_scorecard

out_path = Path(sys.argv[1])

retriever = Retriever.from_pretrained("v0.1.0")
agent = TherapyAgent(model="claude-opus-4-7")

results = []
for case in load_cases():
    context = retriever.retrieve(case.disease_gene, k=10)
    hypotheses = agent.propose(case.disease_gene, context)
    results.append(score_case(case, hypotheses))

out_path.parent.mkdir(parents=True, exist_ok=True)
render_scorecard(results, out_path)
print(f"Wrote {out_path}")
PY

echo
echo "Done. Open ${OUT} in a browser."
