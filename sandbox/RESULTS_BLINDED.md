# Blinded v0.4 results: real biology for candidate interactors

**Backend:** local Llama-3.2-3B-Instruct (Q4_K_M GGUF, llama-cpp-python, CPU).  
**Test set:** 10 YAML benchmark cases in `therapy-agent/benchmarks/`.  
**Input per case:** `gene + mutation + disease_phenotype`.

## What changed vs v0.3

v0.3 fixed the curated-DrugBank leakage but had a key-mismatch bug in
`strategy_synthesis` (read `chembl_compounds`, the schema wrote
`chembl_n_active`) so the druggability counts in the prompt were always 0.
And the agent only saw UniProt biology for the disease gene — none for the
candidate interactors it had to choose among. Both fixed in v0.4:

1. New LangGraph node `interactor_biology_lookup` (between
   `druggable_target_search` and `strategy_synthesis`) fetches UniProt
   chunks for the top-5 druggable candidate interactors via the same
   g2p-rag fallback used for the disease gene.
2. `strategy_synthesis` user message reads the new schema correctly and
   renders a per-candidate biology block so the LLM can compare biology
   across plausible targets.
3. The Reactome `pathway_context` one-liner (which v0.3 read into a local
   variable and then discarded) is now surfaced in the prompt.

## Scorecard

| Metric | v0.4 (full biology) | v0.3 (disease-gene biology only) | v0.2 (leaky) |
|---|---|---|---|
| Target recovery | **3 / 10** (Wilson CI 11-60%) | 4 / 10 | 7 / 10 |
| Modality also correct | 3 / 10 | 2 / 10 | not measured |
| Citation also correct | 4 / 10 | 4 / 10 | not measured |
| Full (target + modality + citation) | 0 / 10 | 0 / 10 | not measured |
| Baseline: predict-disease-gene | 6 / 10 | 6 / 10 | -- |
| Baseline: first-Reactome-interactor | 6 / 10 | 6 / 10 | -- |

### The metric that matters: hard cases (target != disease gene)

- **v0.4: 3 / 5 hard cases recovered** (BRD4780, Ekterly, POMC, Porphyria, SMA)
- v0.3: 2 / 5 hard cases
- Disease-gene baseline: **0 / 5** by construction
- Easy cases (target == disease gene): 0 / 5

On the cases where reasoning is actually required (target != disease gene),
v0.4 recovers 3 of 5. Adding biology for candidate interactors moved the
model from 'pick the disease gene by default' toward 'reason about which
biology fits the mechanism' — that helped porphyria (HMBS -> ALAS1) but
hurt fh_pcsk9 and scd_hbb where the disease gene was the right answer all
along and the model over-reasoned into a partner.

## Per-case

| # | Case | Type | Gene | Expected | Predicted | Target? | Modality? | Citation? |
|---|---|---|---|---|---|---|---|---|
| 1 | `brd4780_umod` | hard | UMOD | TMED9 | `TMED9` | Y | N | Y |
| 2 | `ekterly_serping1` | hard | SERPING1 | KLKB1 | `C1R` | N | Y | N |
| 3 | `als_sod1` | easy | SOD1 | SOD1 | `CCS` | N | N | Y |
| 4 | `dmd_exon51` | easy | DMD | DMD | `DTNA` | N | Y | N |
| 5 | `fabry_gla` | easy | GLA | GLA | `NPC1` | N | N | N |
| 6 | `fh_pcsk9` | easy | PCSK9 | PCSK9 | `IDOL` | N | N | N |
| 7 | `obesity_pomc` | hard | POMC | MC4R | `MC4R` | Y | N | Y |
| 8 | `porphyria_alas1` | hard | HMBS | ALAS1 | `ALAS1` | Y | N | Y |
| 9 | `scd_hbb` | easy | HBB | HBB | `HBA1` | N | Y | N |
| 10 | `sma_smn1` | hard | SMN1 | SMN2 | `GEMIN3` | N | N | N |

## Rationales (truncated)

### brd4780_umod (hard) -- RECOVERED

- Gene: UMOD, expected: TMED9, predicted: `TMED9`
- Mechanism: lof|misfolding  |  Modality: Chaperone  |  Confidence: 0.80
- Rationale: TMED9 is involved in protein folding and quality control in the endoplasmic reticulum, which is relevant to the misfolding of UMOD protein. A pharmacological chaperone binding to TMED9 could help restore proper protein folding and reduce the toxicity associated with UMOD misfolding.

### ekterly_serping1 (hard) -- MISS

- Gene: SERPING1, expected: KLKB1, predicted: `C1R`
- Mechanism: lof  |  Modality: inhibitor  |  Confidence: 0.90
- Rationale: The C1R protein is a key component of the complement pathway, and its deficiency leads to hereditary angioedema. The C1R protein is inhibited by the C1 esterase inhibitor, which is a well-established treatment for hereditary angioedema. Therefore, targeting the C1R protein with an inhibitor is a logical therapeutic strategy for treating hereditary angioedem...

### als_sod1 (easy) -- MISS

- Gene: SOD1, expected: SOD1, predicted: `CCS`
- Mechanism: dominant_negative  |  Modality: chaperone  |  Confidence: 0.90
- Rationale: The dominant-negative mutation in SOD1 leads to a toxic protein product that interferes with wild-type SOD1 activity. CCS is a homodimer that interacts with SOD1 and regulates its activity. A pharmacological chaperone binding to CCS could restore the normal activity of SOD1 and prevent the formation of toxic aggregates.

### dmd_exon51 (easy) -- MISS

- Gene: DMD, expected: DMD, predicted: `DTNA`
- Mechanism: lof  |  Modality: inhibitor | activator | chaperone | siRNA | ASO | gene_therapy | crispr | modulator | replacement  |  Confidence: 0.80
- Rationale: DTNA is a key component of the dystrophin-associated glycoprotein complex, and its loss of function is associated with Duchenne muscular dystrophy. Targeting DTNA could potentially restore muscle function in patients with DMD.

### fabry_gla (easy) -- MISS

- Gene: GLA, expected: GLA, predicted: `NPC1`
- Mechanism: misfolding  |  Modality: inhibitor  |  Confidence: 0.80
- Rationale: NPC1 is a cholesterol transporter that is essential for lysosomal cholesterol homeostasis. The mutation in GLA leads to misfolding and accumulation of Gb3 in lysosomes, causing cellular stress and disease phenotype. Targeting NPC1 with an inhibitor can help restore cholesterol homeostasis and alleviate disease symptoms.

### fh_pcsk9 (easy) -- MISS

- Gene: PCSK9, expected: PCSK9, predicted: `IDOL`
- Mechanism: gof|misfolding  |  Modality: cargo receptor modulation  |  Confidence: 0.80
- Rationale: The mechanism of IDOL's interaction with PCSK9 suggests that IDOL could be a cargo receptor that promotes the degradation of PCSK9, thereby reducing its toxic activity. This is consistent with the misfolding of PCSK9 leading to its toxic activity.

### obesity_pomc (hard) -- RECOVERED

- Gene: POMC, expected: MC4R, predicted: `MC4R`
- Mechanism: lof  |  Modality: inhibitor  |  Confidence: 0.90
- Rationale: The POMC mutation leads to the absence of ACTH/MSH peptides, resulting in the loss of function of the POMC protein. MC4R is a downstream effector of POMC and plays a crucial role in regulating energy homeostasis. Targeting MC4R with an inhibitor can help to restore energy balance and reduce body weight in individuals with POMC deficiency.

### porphyria_alas1 (hard) -- RECOVERED

- Gene: HMBS, expected: ALAS1, predicted: `ALAS1`
- Mechanism: lof  |  Modality: inhibitor  |  Confidence: 0.80
- Rationale: The HMBS gene encodes a protein that is crucial for the biosynthesis of heme. A heterozygous loss-of-function mutation in HMBS leads to the accumulation of toxic ALA/PBG intermediates when ALAS1 is induced. The downstream effector of this loss-of-function is ALAS1 itself, which drives the symptom. Therefore, the therapeutic target is ALAS1, an inhibitor of ...

### scd_hbb (easy) -- MISS

- Gene: HBB, expected: HBB, predicted: `HBA1`
- Mechanism: gof  |  Modality: inhibitor  |  Confidence: 0.80
- Rationale: The mechanism of the disease is a gain-of-function in the HBA1 protein, which is a regulatory enzyme that degrades or modifies another protein. The downstream effector of this enzyme is the HBA2 protein, which is not the target of the disease. Therefore, the target is the HBA1 protein, which can be inhibited to correct the disease.

### sma_smn1 (hard) -- MISS

- Gene: SMN1, expected: SMN2, predicted: `GEMIN3`
- Mechanism: lof  |  Modality: pharmacological chaperone  |  Confidence: 0.80
- Rationale: GEMIN3 is a core component of the SMN complex and has been shown to interact with SMN1. Pharmacological chaperones targeting GEMIN3 could potentially restore the function of the SMN complex and alleviate the symptoms of SMA.
