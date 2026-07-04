#!/usr/bin/env python3
"""Fail if therapy-agent system prompts contain benchmark answer tokens.

The check is intentionally static and conservative. It scans string literals
passed as ``system=...`` in ``therapy-agent/src/therapy_agent`` and compares
them with target symbols and specific aliases from the dev, val, and
adversarial YAML cases.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import]


_HGNC_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")

_SYMBOL_BLOCKLIST = {
    "ACTH", "ADP", "AAV", "AAV9", "ASO", "ATP", "BF16", "CAMP", "CI",
    "CI95", "CNS", "CRH", "DNA", "ER", "FDA", "FDR", "FP16", "GDP",
    "GOF", "GPCR", "GTP", "HGNC", "ICH", "LLM", "LOF", "MRNA", "NME",
    "PCR", "PTM", "Q4", "Q8", "RAG", "RNA", "SC3", "TBD", "VUS",
}

_GENERIC_ALIASES = {
    "activator", "agonist", "antagonist", "antibody", "aso",
    "cargo receptor", "chaperone", "crispr", "enhancer", "enzyme",
    "gene", "gene therapy", "inhibitor", "ligand", "modulator", "mrna",
    "protein", "receptor", "replacement", "sirna", "small molecule",
    "splice", "stabilizer", "transgene",
}


@dataclass(frozen=True)
class Prompt:
    label: str
    text: str


@dataclass(frozen=True)
class LeakToken:
    token: str
    kind: str
    case_id: str
    split: str
    target: str


def therapy_agent_root(repo_root: Path, explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("THERAPY_AGENT_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.extend([
        repo_root / "therapy-agent",
        repo_root.parent / "therapy-agent",
    ])
    for path in candidates:
        if (path / "src" / "therapy_agent").exists():
            return path.resolve()
    tried = "\n  - ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"Could not locate therapy-agent. Tried:\n  - {tried}")


def _split_for(path: Path) -> str:
    parts = set(path.parts)
    if "heldout_2024_2025" in parts:
        return "val"
    if "adversarial" in parts:
        return "adversarial"
    return "dev"


def _specific_alias(alias: str) -> bool:
    text = " ".join((alias or "").strip().split())
    if len(text) < 5:
        return False
    lower = text.lower()
    if lower in _GENERIC_ALIASES:
        return False
    if _HGNC_RE.fullmatch(text):
        return False
    if any(ch.isdigit() for ch in text):
        return True
    if "-" in text:
        return True
    if " receptor" in lower or "factor " in lower:
        return True
    if re.search(r"(mab|nib|cept|tide|siran|rsen|giran|stat|nide)$", lower):
        return True
    if text[:1].isupper() and text[1:].islower():
        return True
    return False


def leak_tokens_from_cases(benchmarks: Path) -> list[LeakToken]:
    tokens: dict[tuple[str, str, str], LeakToken] = {}
    for path in sorted(benchmarks.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(doc, dict) or "expected_outputs" not in doc:
            continue
        exp = doc.get("expected_outputs") or {}
        case_id = str(doc.get("id") or path.stem)
        split = _split_for(path)
        target = str(exp.get("target_protein") or "")
        fields = [target]
        fields.extend(str(x) for x in (exp.get("target_aliases") or []))
        fields.extend(str(x) for x in (exp.get("valid_targets") or []))

        for field in fields:
            for symbol in _HGNC_RE.findall(field or ""):
                if symbol in _SYMBOL_BLOCKLIST:
                    continue
                key = (symbol, case_id, "symbol")
                tokens[key] = LeakToken(symbol, "symbol", case_id, split, target)
            if _specific_alias(field):
                key = (field, case_id, "alias")
                tokens[key] = LeakToken(field, "alias", case_id, split, target)
    return sorted(tokens.values(), key=lambda t: (t.token.lower(), t.case_id))


def _literal_assignments(tree: ast.AST) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value.value
    return out


def system_prompts(source_root: Path) -> list[Prompt]:
    prompts: list[Prompt] = []
    for path in sorted(source_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        literals = _literal_assignments(tree)
        rel = path.relative_to(source_root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "system":
                    continue
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    prompts.append(Prompt(f"{rel}:{kw.value.lineno}", kw.value.value))
                elif isinstance(kw.value, ast.Name) and kw.value.id in literals:
                    prompts.append(Prompt(f"{rel}:{kw.value.id}", literals[kw.value.id]))
    return prompts


def _contains(prompt: str, token: LeakToken) -> bool:
    if token.kind == "symbol":
        pattern = rf"(?<![A-Za-z0-9]){re.escape(token.token)}(?![A-Za-z0-9])"
        return re.search(pattern, prompt) is not None
    pattern = rf"(?<![A-Za-z0-9]){re.escape(token.token)}(?![A-Za-z0-9])"
    return re.search(pattern, prompt, flags=re.IGNORECASE) is not None


def lint(agent_root: Path) -> int:
    prompts = system_prompts(agent_root / "src" / "therapy_agent")
    if not prompts:
        print("FAIL: no system prompts found")
        return 1

    tokens = leak_tokens_from_cases(agent_root / "benchmarks")
    failures: list[tuple[Prompt, LeakToken]] = []
    for prompt in prompts:
        for token in tokens:
            if _contains(prompt.text, token):
                failures.append((prompt, token))

    if failures:
        print("FAIL: benchmark answer tokens found in therapy-agent system prompts")
        for prompt, token in failures:
            print(
                f"  {prompt.label}: {token.kind} {token.token!r} "
                f"from {token.split}/{token.case_id} target={token.target!r}"
            )
        return 1

    print(
        f"OK: {len(prompts)} system prompt(s) contain none of "
        f"{len(tokens)} benchmark target token(s)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--therapy-agent-root", help="path to therapy-agent checkout")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        root = therapy_agent_root(repo_root, args.therapy_agent_root)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return lint(root)


if __name__ == "__main__":
    raise SystemExit(main())
