# Blinded v0.3 results: therapy-agent + Llama-3.2-3B, leakage-stripped

**Backend:** local Llama-3.2-3B-Instruct (Q4_K_M GGUF, llama-cpp-python, CPU).  
**Test set:** 10 YAML benchmark cases in `therapy-agent/benchmarks/`.  
**Input per case:** `gene + mutation + disease_phenotype`. No drug or target leaks.

## What changed vs v0.2 (the 7/10 number)

Audit found three leakage paths that v0.2 was unintentionally exploiting:

1. `tools/drugbank_query.py` was a static dict mapping every benchmark gene
   to its FDA-approved drug name + mechanism string. That dict was serialized
   into the `strategy_synthesis` user prompt as `Approved drugs found: [...]`.
   Replaced with a coarse druggability-flag-only lookup, no drug names.
2. `tools/reactome_query.py` `GENE_PATHWAY_FALLBACK` had curated entries with
   narrative `pathway_context` strings naming the FDA drug and strategy. The
   narrative strings were already neutralized in v0.2; the curated interactor
   lists kept (real biology).
3. `nodes/druggable_target_search.py` hardcoded `qc_genes = [TMED9, TMED2, ...]`
   when mechanism = misfolding, hand-placing the BRD4780 answer in the candidate
   set. Removed.

Additionally, g2p-rag retrieval now actually flows in: when the g2p-rag
ChromaDB index isn't available, the fallback hits UniProt REST directly and
returns chunks shaped like g2p-rag would (FUNCTION / PATHWAY / SUBUNIT / PTM /
LIPIDATION / DISEASE). The model sees real biology, not the FDA answer.

## Scorecard

| Metric | Value |
|---|---|
| Target recovery | **4 / 10** (95% Wilson CI 17–69%) |
| Modality also correct | 2 / 10 |
| Citation also correct | 4 / 10 |
| Full (target + modality + citation) | 0 / 10 |
| Baseline: always-predict-disease-gene | 6 / 10 |
| Baseline: first-Reactome-interactor | 6 / 10 |
| Total wall time | 953s |

**The agent UNDERPERFORMS the trivial 'predict the disease gene' baseline**
(4/10 vs 6/10) when leakage is removed. This is the result the v0.2 numbers
hid. The 3B model over-reasons to downstream partners on cases where the
FDA target is the disease gene itself, and under-reasons on cases where the
FDA target is a specific downstream protein.

## Per-case

| # | Case | Gene | Expected | Predicted | Target? | Modality? | Citation? |
|---|---|---|---|---|---|---|---|
| 1 | `brd4780_umod` | UMOD | TMED9 | `TMED9` | Y | N | Y |
| 2 | `ekterly_serping1` | SERPING1 | KLKB1 | `C1S` | N | Y | N |
| 3 | `als_sod1` | SOD1 | SOD1 | `CCS` | N | N | Y |
| 4 | `dmd_exon51` | DMD | DMD | `UTRN` | N | N | N |
| 5 | `fabry_gla` | GLA | GLA | `NPC1` | N | N | N |
| 6 | `fh_pcsk9` | PCSK9 | PCSK9 | `PCSK9` | Y | Y | N |
| 7 | `obesity_pomc` | POMC | MC4R | `MC4R` | Y | N | Y |
| 8 | `porphyria_alas1` | HMBS | ALAS1 | `HMBS` | N | N | Y |
| 9 | `scd_hbb` | HBB | HBB | `HBB` | Y | N | N |
| 10 | `sma_smn1` | SMN1 | SMN2 | `GEMIN3` | N | N | N |

## Per-case rationales

### brd4780_umod -- RECOVERED

- Gene: UMOD
- Expected target: TMED9
- Predicted target: `TMED9` (chaperone, conf 0.80)
- Mechanism: lof|misfolding
- Rationale: TMED9 is a cargo receptor protein that plays a key role in the ER retention of misfolded proteins, which is consistent with the mechanism of UMOD protein misfolding and ER retention. Targeting TMED9 with a pharmacological chaperone could potentially correct the disease by reducing the accumulation of misfolded UMOD protein in the ER.

### ekterly_serping1 -- MISS

- Gene: SERPING1
- Expected target: KLKB1
- Predicted target: `C1S` (inhibitor, conf 0.90)
- Mechanism: lof
- Rationale: The molecular mechanism of hereditary angioedema due to C1 esterase inhibitor deficiency is a loss of function of the C1S protein, which is a key regulator of the complement pathway. Targeting the C1S protein with an inhibitor can correct the disease by blocking the downstream effector of the C1S protein, which is the complement pathway. This is consistent with pattern 1, whic...

### als_sod1 -- MISS

- Gene: SOD1
- Expected target: SOD1
- Predicted target: `CCS` (chaperone, conf 0.80)
- Mechanism: dominant_negative
- Rationale: The dominant-negative SOD1 mutation leads to misfolding and aggregation, which can be mitigated by a pharmacological chaperone that binds to the disease gene's own protein, CCS. This approach targets the CCS protein, which is involved in the degradation of the toxic SOD1 variant.

### dmd_exon51 -- MISS

- Gene: DMD
- Expected target: DMD
- Predicted target: `UTRN` (chaperone, conf 0.80)
- Mechanism: lof
- Rationale: The mechanism of DMD is lof due to a frameshift mutation in the dystrophin gene. The UTRN protein is a component of the dystrophin-associated glycoprotein complex and interacts with the dystrophin protein. Given that the UTRN protein is involved in the dystrophin pathway and the mechanism is lof, a pharmacological chaperone binding to the UTRN protein could correct the disease...

### fabry_gla -- MISS

- Gene: GLA
- Expected target: GLA
- Predicted target: `NPC1` (inhibitor, conf 0.80)
- Mechanism: misfolding
- Rationale: NPC1 is a key regulator of Gb3 transport in lysosomes, and its inhibition can reduce Gb3 accumulation. This is consistent with the mechanism of Fabry disease, where NPC1's function is disrupted, leading to Gb3 accumulation and disease phenotype.

### fh_pcsk9 -- RECOVERED

- Gene: PCSK9
- Expected target: PCSK9
- Predicted target: `PCSK9` (chaperone | siRNA | ASO, conf 0.80)
- Mechanism: gof|misfolding
- Rationale: The gain-of-function missense mutation in PCSK9 leads to enhanced LDLR degradation, causing familial hypercholesterolemia. The mutation results in a toxic protein product that misfolds and aggregates, disrupting normal cellular function and contributing to the disease phenotype. Since the mechanism is gof in a regulatory enzyme that degrades or modifies another protein, causin...

### obesity_pomc -- RECOVERED

- Gene: POMC
- Expected target: MC4R
- Predicted target: `MC4R` (inhibitor, conf 0.90)
- Mechanism: lof
- Rationale: The POMC mutation leads to the absence of ACTH/MSH peptides, resulting in the loss of function of the POMC protein. However, the downstream MC4R receptor still works, and its activation is essential for regulating energy homeostasis. Therefore, targeting the MC4R receptor with an agonist that bypasses the missing ligand can correct the disease phenotype.

### porphyria_alas1 -- MISS

- Gene: HMBS
- Expected target: ALAS1
- Predicted target: `HMBS` (pharmacological chaperone, conf 0.80)
- Mechanism: lof
- Rationale: The HMBS protein is a regulatory enzyme in the heme biosynthetic pathway. The nonsense mutation in HMBS leads to a truncated, non-functional protein, resulting in the accumulation of toxic ALA/PBG intermediates when ALAS1 is induced. This loss-of-function causes acute intermittent porphyria, a disease characterized by life-threatening neurovisceral attacks triggered by various...

### scd_hbb -- RECOVERED

- Gene: HBB
- Expected target: HBB
- Predicted target: `HBB` (pharmacological chaperone, conf 0.80)
- Mechanism: gof
- Rationale: The HBB gene encodes for hemoglobin A, a heterotetramer of two alpha chains and two beta chains. The mutation c.20A>T (p.Glu6Val) leads to a gain-of-function, where the hemoglobin S protein polymerizes under hypoxic conditions. A pharmacological chaperone targeting the HBB protein could potentially correct the misfolding and aggregation of the mutant protein, restoring normal ...

### sma_smn1 -- MISS

- Gene: SMN1
- Expected target: SMN2
- Predicted target: `GEMIN3` (augmentation, conf 0.80)
- Mechanism: lof
- Rationale: Given the mechanism of SMA1, which is caused by the loss-of-function of the SMN protein, and the fact that GEMIN3 is a key component of the spliceosome, it is plausible that GEMIN3 is a compensatory paralog that is silenced by a repressor in SMA1. Targeting GEMIN3 via augmentation could potentially restore its expression and improve SMA1 symptoms.

## How to read this

Two cases where the agent _does_ beat the disease-gene baseline:
- `brd4780_umod`: agent picked TMED9 from real UniProt SUBUNIT/INTERACTORS evidence (UMOD's interactors include TMED9/TMED2/TMED10 in Reactome).
- `obesity_pomc`: agent picked MC4R by reasoning from the melanocortin pathway in g2p-rag chunks.

Five cases where the agent over-reasons past the right answer:
- `ekterly_serping1`: picked C1S (a complement protease SERPING1 inhibits) instead of KLKB1 (the kallikrein-kinin axis protease).
- `als_sod1`: picked CCS (copper chaperone for SOD1) instead of SOD1 mRNA.
- `dmd_exon51`: picked UTRN (utrophin, a paralog) instead of DMD exon skip.
- `fabry_gla`: picked NPC1 (lysosomal cholesterol transporter) instead of GLA chaperone.
- `porphyria_alas1`: picked HMBS (disease gene itself) instead of ALAS1 upstream knockdown.
- `sma_smn1`: picked GEMIN3 (SMN complex partner) instead of SMN2 splicing.

All of these are biologically adjacent but clinically wrong — the kind of mistake a small model makes when it can't disambiguate among several plausible candidates.