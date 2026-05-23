# assets

This directory holds rendered artifacts referenced from the top-level README.

| File | How to (re)generate |
|---|---|
| `scorecard_v0.1.0.html` | `bash scripts/run_e2e.sh` (or run [`demos/03_full_benchmark.ipynb`](../demos/03_full_benchmark.ipynb)) |
| `architecture.png` | Render the mermaid block at the top of the [README](../README.md) — e.g. `mmdc -i README.md -o architecture.png` |
| `demo.gif` | `bash scripts/record_demo.sh` (requires `asciinema` + `agg`) |

Binary assets (`architecture.png`, `demo.gif`) are produced by the scripts above and committed only when refreshed. If they are missing, the regeneration commands are the source of truth.
