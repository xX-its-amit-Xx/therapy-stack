# Contributing

## Prompt And Benchmark Safety

Any prompt change that touches benchmark-case biology must pass the static
leakage checks before merge:

```bash
python scripts/benchmark_lint.py
python scripts/prompt_leakage_lint.py
```

`prompt_leakage_lint.py` scans `therapy-agent` system prompts for target
symbols and specific aliases from dev, val, and adversarial YAML cases. If the
prompt needs a mechanism example, describe the mechanism class generically
instead of naming a benchmark target.

## Result Claims

Do not add or update a public score, percentage, wall time, or chart by hand.
Add a committed result JSON first, add or update the corresponding
`results/ledger.json` entry, then render docs or chart data from the ledger.
