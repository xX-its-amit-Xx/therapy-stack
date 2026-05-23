#!/usr/bin/env bash
# Install all four child packages at the versions pinned in requirements.txt.
#
# Usage: bash scripts/install_all.sh
set -euo pipefail

cd "$(dirname "$0")/.."

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "Installed:"
python -m pip list | grep -E "^(g2p-rag|fda-strategy-triples|therapy-agent|bio-rag-eval|anthropic|jupyter) "
