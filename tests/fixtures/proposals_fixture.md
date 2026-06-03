# Therapy Proposals Fixture

This fixture file contains three candidate proposals used to exercise the
citation-verification scorer across its OK / WARN / FAIL code paths.

## Proposal 1: Targeting AKT1 for triple-negative breast cancer via allosteric kinase inhibition

AKT1 is a serine/threonine kinase whose hyperactivation drives proliferation
in a subset of triple-negative breast cancers. The UniProt record states that
the "canonical AKT1 isoform encodes a protein of approximately 480 residues",
which bounds the domain architecture available for allosteric pocket design.
[chunk P31749:protein_summary:1-480: protein_summary AKT1 1-480]

We therefore propose a covalent allosteric inhibitor anchored outside the
ATP-binding cleft to improve isoform selectivity over AKT2 and AKT3.

## Proposal 2: Targeting AKT1 for PIK3CA-mutant tumors via kinase-domain disruption

The AKT1 kinase domain spans roughly residues 150 through 408, covering the
catalytic core that phosphorylates downstream substrates such as TSC2 and
FOXO1. We propose a domain-disrupting peptide therapeutic that competes with
substrate docking on this segment.
[chunk P31749:domain:150-408: domain AKT1 150-408]

This approach should complement existing PI3K inhibitors by blocking the
node immediately downstream of PIP3 generation.

## Proposal 3: Targeting NONEXIST for a synthetic disease via a fabricated modality

NONEXIST is described in our index as a hypothetical kinase whose
N-terminal 100 residues are claimed to form a regulatory module. We propose
a small-molecule binder against this purported region as a negative-control
proposal that should fail citation verification.
[chunk Q9XXXX:domain:1-100: domain NONEXIST 1-100]
