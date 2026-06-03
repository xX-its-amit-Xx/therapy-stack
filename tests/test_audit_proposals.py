"""Regression tests for scripts/audit_proposals.py.

These tests invoke the auditor as a subprocess (so we cover the real CLI
contract, exit codes, and argument parsing) against the live g2p-rag
Chroma collection. They are skipped automatically if the index isn't
reachable -- this keeps the smoke-run / CI matrix happy on machines that
don't carry the 948-chunk Chroma store.

Run with: pytest tests/test_audit_proposals.py -v -m audit_proposals
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# ── paths ─────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
THERAPY_STACK_ROOT = _HERE.parent
AUDIT_SCRIPT = THERAPY_STACK_ROOT / "scripts" / "audit_proposals.py"
FIXTURE = _HERE / "fixtures" / "proposals_fixture.md"

# Chroma path resolves via env var override (CI / dev box flexibility) or
# falls back to ../g2p-rag/data/chroma relative to the therapy-stack root.
# Matches the layout assumed by scripts/audit_proposals.py:DEFAULT_CHROMA_DIR.
G2P_RAG_CHROMA_PATH = os.environ.get(
    "G2P_CHROMA_PATH",
    str((THERAPY_STACK_ROOT.parent / "g2p-rag" / "data" / "chroma").resolve()),
)

# Mark every test in this module so the suite can be deselected on smoke runs
# with `pytest -m "not audit_proposals"`.
pytestmark = pytest.mark.audit_proposals


# ── module-level guard: skip if the chroma collection is unreachable ──────────

@pytest.fixture(scope="module", autouse=True)
def _require_g2p_rag_chroma():
    """Skip every test in this module if g2p-rag's Chroma index is missing.

    We try to open the collection the auditor will open. If anything goes
    wrong -- import error, missing path, missing collection -- we skip
    rather than fail, because these are integration tests, not unit tests.
    """
    try:
        import chromadb  # noqa: F401
    except ImportError as e:
        pytest.skip(f"chromadb not installed: {e}")

    if not Path(G2P_RAG_CHROMA_PATH).exists():
        pytest.skip(
            f"g2p-rag chroma index not found at {G2P_RAG_CHROMA_PATH}; "
            f"set G2P_CHROMA_PATH to override"
        )

    try:
        import chromadb
        client = chromadb.PersistentClient(path=G2P_RAG_CHROMA_PATH)
        coll = client.get_collection("g2p_proteins")
        if coll.count() == 0:
            pytest.skip(
                f"g2p_proteins collection at {G2P_RAG_CHROMA_PATH} is empty"
            )
    except Exception as e:
        pytest.skip(f"could not open g2p_proteins collection: {e}")

    yield


# ── helpers ───────────────────────────────────────────────────────────────────

def _run_auditor(*extra_args: str, proposals_path: str | None = None):
    """Invoke scripts/audit_proposals.py as a subprocess and return the result."""
    target = proposals_path if proposals_path is not None else str(FIXTURE)
    cmd = [
        sys.executable,
        str(AUDIT_SCRIPT),
        target,
        "--chroma-path",
        G2P_RAG_CHROMA_PATH,
        *extra_args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(THERAPY_STACK_ROOT),
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test_audit_runs_on_fixture_and_finds_three_proposals():
    """The auditor should parse and report on all three '## Proposal N:' blocks.

    The fixture file also has a preamble block before the first heading, so
    the auditor's total block count is 4. We count only the real proposal
    blocks here (lines beginning with '## Proposal'), which must equal 3.
    """
    result = _run_auditor()
    assert AUDIT_SCRIPT.exists(), f"auditor missing: {AUDIT_SCRIPT}"
    assert FIXTURE.exists(), f"fixture missing: {FIXTURE}"

    stdout = result.stdout
    # Each real proposal block surfaces in stdout as a line beginning with
    # '## Proposal' (the auditor echoes the heading verbatim). Counting these
    # is more robust than reading the SUMMARY total, which also includes the
    # synthetic '(preamble)' block.
    proposal_lines = [
        line for line in stdout.splitlines()
        if line.startswith("## Proposal")
    ]
    assert len(proposal_lines) == 3, (
        f"expected 3 '## Proposal' blocks in auditor output, "
        f"got {len(proposal_lines)}\n--- stdout ---\n{stdout}"
    )


def test_audit_exit_code_is_1_when_fake_citation_present():
    """The fixture's Proposal 3 cites a chunk that doesn't exist in the index.

    The auditor must surface this as a FAIL and exit with status 1 (the
    CI-blocking exit code per the script's docstring).
    """
    result = _run_auditor()
    assert result.returncode == 1, (
        f"expected returncode 1 with fake citation present, "
        f"got {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_audit_strict_flag_promotes_paraphrase_to_fail():
    """Under --strict, an unmatched-quote WARN must be promoted to FAIL.

    The fixture's Proposal 1 has a paraphrased quote whose text isn't a
    verbatim substring of the cited chunk. In lenient mode that's a WARN
    (and on its own would exit 0); under --strict it becomes a FAIL and
    contributes to the exit-1 result. We verify both pieces: exit code 1,
    and that the auditor's mode banner reflects strict.
    """
    result = _run_auditor("--strict")
    assert result.returncode == 1, (
        f"expected returncode 1 in strict mode, got {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    # Cross-check that the auditor actually ran in strict mode.
    assert "strict" in result.stdout.lower(), (
        f"auditor did not report strict mode in stdout:\n{result.stdout}"
    )


def test_audit_with_only_real_ok_citation_exits_clean(tmp_path):
    """A proposal file with only a real, resolvable, exact-quote citation
    must produce zero FAILs and zero WARNs, exit 0.

    We use Proposal 2's citation (AKT1 kinase domain 150-408), which is a
    real chunk in the index, and we add no quotes so there's nothing to
    paraphrase-check.
    """
    clean = tmp_path / "ok_only.md"
    clean.write_text(
        "## Proposal Clean: AKT1 kinase-domain disruption\n"
        "\n"
        "We propose a domain-disrupting peptide therapeutic that competes\n"
        "with substrate docking on the AKT1 kinase domain.\n"
        "[chunk P31749:domain:150-408: domain AKT1 150-408]\n",
        encoding="utf-8",
    )
    result = _run_auditor(proposals_path=str(clean))
    assert result.returncode == 0, (
        f"expected returncode 0 on clean single-proposal file, "
        f"got {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_audit_handles_missing_file_with_exit_2():
    """An invocation against a non-existent path is an *invocation* error, not
    an audit failure. The auditor distinguishes these with exit code 2 so CI
    can tell 'you typo'd the path' apart from 'a real citation failed'.
    """
    missing = THERAPY_STACK_ROOT / "tests" / "fixtures" / "this_file_does_not_exist.md"
    assert not missing.exists(), (
        "test precondition violated: the 'missing' path actually exists; "
        "rename it or delete it before re-running"
    )
    result = _run_auditor(proposals_path=str(missing))
    assert result.returncode == 2, (
        f"expected returncode 2 for missing input file, "
        f"got {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
