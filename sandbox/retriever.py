"""
UniProt-backed retriever.

Given a gene symbol, fetch the reviewed (SwissProt) human entry and return
function/keyword text. This stands in for `g2p-rag.retrieve(...)` for the
end-to-end demo, since g2p-rag requires a pre-built ChromaDB index we
don't have on this machine.

UniProt is what g2p-rag is ultimately built on top of, so the *kind* of
context this returns is what the real retriever would surface — just
without the dense+sparse RAG layer.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import requests


UNIPROT = "https://rest.uniprot.org/uniprotkb/search"

_PUBMED_CITE_RE = re.compile(r"\(?\s*PubMed:\d+(?:\s*,\s*PubMed:\d+)*\s*\)?")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


def _clean(text: str, *, max_chars: int = 700) -> str:
    """Strip dense PubMed citations and collapse whitespace, then truncate."""
    out = _PUBMED_CITE_RE.sub("", text)
    out = _MULTI_SPACE_RE.sub(" ", out).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0] + "..."
    return out


@dataclass
class GeneContext:
    gene: str
    uniprot_acc: str
    protein_name: str
    function_texts: list[str]
    pathway_texts: list[str]
    subunit_texts: list[str]
    ptm_texts: list[str]
    lipidation_sites: list[str]
    disease_summaries: list[str]
    keywords: list[str]
    raw_url: str

    def as_prompt_context(self, max_chars: int = 2800) -> str:
        parts = [f"Gene symbol: {self.gene}",
                 f"Protein name: {self.protein_name}",
                 f"UniProt accession: {self.uniprot_acc}",
                 ""]
        if self.function_texts:
            parts.append("FUNCTION:")
            for t in self.function_texts[:3]:
                parts.append(f"- {t}")
            parts.append("")
        if self.pathway_texts:
            parts.append("PATHWAY:")
            for t in self.pathway_texts[:4]:
                parts.append(f"- {t}")
            parts.append("")
        if self.subunit_texts:
            parts.append("SUBUNIT / INTERACTIONS:")
            for t in self.subunit_texts[:3]:
                parts.append(f"- {t}")
            parts.append("")
        if self.ptm_texts:
            parts.append("POST-TRANSLATIONAL MODIFICATIONS:")
            for t in self.ptm_texts[:3]:
                parts.append(f"- {t}")
            parts.append("")
        if self.lipidation_sites:
            parts.append("LIPIDATION SITES:")
            for t in self.lipidation_sites[:5]:
                parts.append(f"- {t}")
            parts.append("")
        if self.disease_summaries:
            parts.append("ASSOCIATED DISEASES:")
            for t in self.disease_summaries[:4]:
                parts.append(f"- {t}")
            parts.append("")
        parts.append(f"KEYWORDS: {', '.join(self.keywords[:25])}")
        out = "\n".join(parts)
        return out[:max_chars]


_FIELDS = ",".join([
    "accession", "gene_names", "protein_name",
    "cc_function", "cc_pathway", "cc_subunit",
    "cc_ptm", "cc_disease",
    "ft_lipid",
    "keyword",
])


def retrieve(gene: str, *, timeout: float = 20.0, retries: int = 2) -> GeneContext:
    """Fetch the reviewed human UniProt entry for *gene* and return a GeneContext."""
    params = {
        "query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
        "fields": _FIELDS,
        "format": "json",
        "size": 1,
    }
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(UNIPROT, params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"UniProt fetch failed for {gene!r}: {last_err}")

    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"No reviewed human UniProt entry for gene {gene!r}.")
    entry = results[0]

    acc = entry.get("primaryAccession", "")
    pname = (entry.get("proteinDescription", {})
                  .get("recommendedName", {})
                  .get("fullName", {})
                  .get("value", ""))

    fn_texts: list[str] = []
    pathway_texts: list[str] = []
    subunit_texts: list[str] = []
    ptm_texts: list[str] = []
    disease_summaries: list[str] = []
    for c in entry.get("comments", []):
        ct = c.get("commentType")
        if ct == "FUNCTION":
            for t in c.get("texts", []):
                v = t.get("value", "").strip()
                if not v:
                    continue
                if v.lower().startswith("(microbial infection)") or "virus" in v.lower()[:60]:
                    continue
                fn_texts.append(_clean(v, max_chars=500))
        elif ct == "PATHWAY":
            for t in c.get("texts", []):
                v = t.get("value", "").strip()
                if v:
                    pathway_texts.append(_clean(v, max_chars=400))
        elif ct == "SUBUNIT":
            for t in c.get("texts", []):
                v = t.get("value", "").strip()
                if v:
                    subunit_texts.append(_clean(v, max_chars=400))
        elif ct == "PTM":
            for t in c.get("texts", []):
                v = t.get("value", "").strip()
                if v:
                    ptm_texts.append(_clean(v, max_chars=500))
        elif ct == "DISEASE":
            dis = c.get("disease", {}) or {}
            name = dis.get("diseaseId", "") or ""
            acronym = dis.get("acronym", "") or ""
            desc = (dis.get("description", "") or "").strip()
            if name or desc:
                head = f"{name} ({acronym})".strip(" ()")
                disease_summaries.append(_clean(f"{head}: {desc}".strip(": "), max_chars=300))

    lipidation_sites: list[str] = []
    for ft in entry.get("features", []):
        if ft.get("type") != "Lipidation":
            continue
        desc = ft.get("description", "") or ""
        loc = ft.get("location", {}) or {}
        start = (loc.get("start") or {}).get("value")
        end = (loc.get("end") or {}).get("value")
        pos = f"{start}" if start == end else f"{start}-{end}"
        lipidation_sites.append(f"{desc} at residue {pos}")

    if not fn_texts:
        for c in entry.get("comments", []):
            if c.get("commentType") == "FUNCTION":
                for t in c.get("texts", []):
                    v = t.get("value", "").strip()
                    if v:
                        fn_texts.append(v)
                        break

    keywords = [k.get("name", "") for k in entry.get("keywords", []) if k.get("name")]
    return GeneContext(
        gene=gene,
        uniprot_acc=acc,
        protein_name=pname,
        function_texts=fn_texts,
        pathway_texts=pathway_texts,
        subunit_texts=subunit_texts,
        ptm_texts=ptm_texts,
        lipidation_sites=lipidation_sites,
        disease_summaries=disease_summaries,
        keywords=keywords,
        raw_url=f"https://www.uniprot.org/uniprotkb/{acc}",
    )


def retrieve_many(genes: list[str]) -> list[GeneContext]:
    """Convenience: retrieve for several genes (used when a case lists multiple)."""
    out: list[GeneContext] = []
    for g in genes:
        try:
            out.append(retrieve(g))
        except RuntimeError:
            continue
    return out


def parse_genes(raw) -> list[str]:
    """Normalize fda-strategy-triples 'associated_genes' to ['SMN1', 'SMN2'].

    The column comes back as a numpy ndarray (when reading parquet) or
    occasionally as a stringified list. Both should produce a clean list."""
    # numpy ndarray, list, tuple — anything iterable that isn't a string.
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    if isinstance(raw, (list, tuple)):
        return [str(g).strip() for g in raw if str(g).strip()]
    if not isinstance(raw, str):
        return []
    cleaned = re.sub(r"[\[\]'\"]", " ", raw)
    return [tok for tok in re.split(r"[\s,]+", cleaned) if tok]
