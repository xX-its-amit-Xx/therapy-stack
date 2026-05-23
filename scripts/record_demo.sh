#!/usr/bin/env bash
# Record a terminal demo of run_e2e.sh using asciinema, then convert the
# .cast file to a GIF using agg.
#
# Usage: bash scripts/record_demo.sh
#
# Requires asciinema (https://asciinema.org) and agg (https://github.com/asciinema/agg).
set -euo pipefail

cd "$(dirname "$0")/.."

CAST="assets/demo.cast"
GIF="assets/demo.gif"

for tool in asciinema agg; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: $tool is not installed." >&2
    echo "  asciinema: pip install asciinema" >&2
    echo "  agg:       https://github.com/asciinema/agg" >&2
    exit 1
  fi
done

mkdir -p assets

echo "Recording demo to ${CAST}. Press Ctrl-D when run_e2e.sh finishes."
asciinema rec --overwrite --command "bash scripts/run_e2e.sh" "$CAST"

echo "Converting ${CAST} → ${GIF}..."
agg --cols 100 --rows 30 --font-size 14 "$CAST" "$GIF"

echo "Done. ${GIF} is ready to embed in README.md."
