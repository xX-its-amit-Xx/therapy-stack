#!/usr/bin/env python3
"""Render scorecard artifacts from results/ledger.json.

This script is intentionally boring: it reads the ledger, verifies each row
against its source JSON when possible, and renders the README scorecard table
plus optional chart data. It never reads numbers from README prose.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


BEGIN = "<!-- BEGIN SCORECARD -->"
END = "<!-- END SCORECARD -->"


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(x: float) -> int:
    return int(round(x * 100))


def load_ledger(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "therapy-stack-results-ledger/v1":
        raise ValueError(f"Unsupported ledger schema: {data.get('schema_version')!r}")
    if not isinstance(data.get("entries"), list):
        raise ValueError("Ledger must contain an entries list")
    return data


def _source_count(source: dict[str, Any]) -> tuple[int | None, int | None]:
    n = source.get("n_cases")
    recovered = source.get("target_recovered", source.get("recovered"))
    if isinstance(n, int) and isinstance(recovered, int):
        return n, recovered
    return None, None


def verify_sources(entries: list[dict[str, Any]], repo_root: Path) -> None:
    for entry in entries:
        source_path = repo_root / entry["source_result_file"]
        if not source_path.exists():
            raise FileNotFoundError(f"{entry['version_tag']}: missing {source_path}")
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source_n, source_recovered = _source_count(source)
        if source_n is not None and source_n != entry["n_cases"]:
            raise ValueError(
                f"{entry['version_tag']}: ledger n_cases={entry['n_cases']} "
                f"but source has {source_n}"
            )
        if source_recovered is not None and source_recovered != entry["recovered_count"]:
            raise ValueError(
                f"{entry['version_tag']}: ledger recovered_count="
                f"{entry['recovered_count']} but source has {source_recovered}"
            )


def table_rows(entries: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| Backend | Split | Target | Wall | Cost |",
        "|---|---|---|---|---|",
    ]
    for entry in entries:
        k = int(entry["recovered_count"])
        n = int(entry["n_cases"])
        lo, hi = wilson_ci(k, n)
        target = f"{k}/{n} ({pct(k / n)}%; 95% CI {pct(lo)}-{pct(hi)}%)"
        wall = entry.get("wall_seconds")
        if isinstance(wall, (int, float)):
            wall_text = f"{round(float(wall) / 60):.0f} min"
        else:
            wall_text = str(wall)
        cost = "local" if str(entry.get("backend", "")).startswith("llama") else "NOT RECORDED"
        rows.append(
            f"| {entry['label']} | {entry['split']} | {target} | {wall_text} | {cost} |"
        )
    return rows


def render_markdown(entries: list[dict[str, Any]]) -> str:
    return "\n".join(table_rows(entries))


def update_readme(readme: Path, table: str) -> None:
    text = readme.read_text(encoding="utf-8")
    start = text.index(BEGIN)
    end = text.index(END, start)
    replacement = f"{BEGIN}\n{table}\n{END}"
    text = text[:start] + replacement + text[end + len(END):]
    readme.write_text(text, encoding="utf-8")


def chart_points(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = []
    for entry in entries:
        k = int(entry["recovered_count"])
        n = int(entry["n_cases"])
        lo, hi = wilson_ci(k, n)
        points.append({
            "version_tag": entry["version_tag"],
            "label": entry["label"],
            "split": entry["split"],
            "model": entry["model"],
            "quantization": entry["quantization"],
            "n_cases": n,
            "recovered_count": k,
            "accuracy": k / n if n else 0.0,
            "wilson_ci": [lo, hi],
            "wall_seconds": entry.get("wall_seconds"),
            "source_result_file": entry["source_result_file"],
        })
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=Path("results/ledger.json"))
    parser.add_argument("--readme", type=Path, help="replace README scorecard block")
    parser.add_argument("--chart-data", type=Path, help="write chart-data JSON")
    parser.add_argument("--all", action="store_true", help="include non-scorecard ledger rows")
    args = parser.parse_args()

    repo_root = args.ledger.resolve().parents[1]
    data = load_ledger(args.ledger)
    entries = data["entries"] if args.all else [
        e for e in data["entries"] if e.get("show_in_scorecard")
    ]
    verify_sources(entries, repo_root)

    table = render_markdown(entries)
    if args.readme:
        update_readme(args.readme, table)
    if args.chart_data:
        args.chart_data.parent.mkdir(parents=True, exist_ok=True)
        args.chart_data.write_text(
            json.dumps(chart_points(entries), indent=2) + "\n",
            encoding="utf-8",
        )
    if not args.readme and not args.chart_data:
        print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
