# Blinded v0.2 results: therapy-agent + Llama-3.2-3B

**Backend:** local Llama-3.2-3B-Instruct (Q4_K_M GGUF, llama-cpp-python, CPU).  
**Test set:** 10 YAML benchmark cases from `therapy-agent/benchmarks/`.  
**Input fields per case:** gene, mutation, disease_phenotype.
No FDA-approved drug or target name is passed to the agent.  
**Wall time:** 823s total (82s/case).  
**Recovered:** 7 / 10 (gold target or alias appears in predicted target_protein).

| # | Case | Gene | Expected target | Predicted target | Recovered |
|---|---|---|---|---|---|
| 1 | `brd4780_umod` | UMOD | TMED9 | `TMED9` | YES |
| 2 | `ekterly_serping1` | SERPING1 | KLKB1 | `KLKB1` | YES |
| 3 | `als_sod1` | SOD1 | SOD1 | `PRDX1` | NO |
| 4 | `dmd_exon51` | DMD | DMD | `SGCA` | NO |
| 5 | `fabry_gla` | GLA | GLA | `GLA` | YES |
| 6 | `fh_pcsk9` | PCSK9 | PCSK9 | `PCSK9` | YES |
| 7 | `obesity_pomc` | POMC | MC4R | `MC4R` | YES |
| 8 | `porphyria_alas1` | HMBS | ALAS1 | `ALAS1` | YES |
| 9 | `scd_hbb` | HBB | HBB | `MYB` | NO |
| 10 | `sma_smn1` | SMN1 | SMN2 | `SMN1` | YES |

## Per-case rationales

### brd4780_umod -- RECOVERED

- Gene: UMOD
- Expected target: TMED9
- Predicted target: `TMED9` (cargo receptor modulator, conf 0.90)
- Predicted mechanism: lof|misfolding
- Rationale: The frameshift mutation in UMOD likely causes a non-toxic protein to misfold and be retained in the ER, leading to cellular stress and contributing to the development of ADTKD. TMED9 is a cargo receptor protein that binds to ER-retained UMOD and promotes its degradation via the ER-associated degradation pathway. Modulating TMED9's activity can help to release UMOD from the ER ...

### ekterly_serping1 -- RECOVERED

- Gene: SERPING1
- Expected target: KLKB1
- Predicted target: `KLKB1` (inhibitor, conf 0.90)
- Predicted mechanism: lof
- Rationale: KLKB1 is a plasma kallikrein inhibitor whose downstream effector drives HAE symptoms. Targeting KLKB1 with an inhibitor reduces the amount of toxic plasma kallikrein in the system, thereby alleviating symptoms.

### als_sod1 -- MISS

- Gene: SOD1
- Expected target: SOD1
- Predicted target: `PRDX1` (inhibitor, conf 0.80)
- Predicted mechanism: dominant_negative
- Rationale: PRDX1 is a downstream effector of SOD1 and has been shown to have antioxidant properties. Inhibiting PRDX1 can help reduce the toxic effects of SOD1 aggregates in motor neurons, making it a potential therapeutic target for familial ALS.

### dmd_exon51 -- MISS

- Gene: DMD
- Expected target: DMD
- Predicted target: `SGCA` (inhibitor, conf 0.90)
- Predicted mechanism: lof
- Rationale: The mechanism of lof in a regulatory enzyme (DTNA, DTNB, SNTA1, DAG1) whose downstream effector (NOS1) drives the symptom. Targeting the unbraked downstream effector enzyme (NOS1) can correct the disease. The precedent drugs targeting NOS1 are already approved for other indications.

### fabry_gla -- RECOVERED

- Gene: GLA
- Expected target: GLA
- Predicted target: `GLA` (chaperone, conf 0.90)
- Predicted mechanism: misfolding
- Rationale: The mutation reduces alpha-galactosidase A stability, leading to misfolding and accumulation of Gb3 in lysosomes. Migalastat (Galafold) is a pharmacological chaperone that stabilizes GLA, correcting the misfolding and restoring normal lysosomal function.

### fh_pcsk9 -- RECOVERED

- Gene: PCSK9
- Expected target: PCSK9
- Predicted target: `PCSK9` (siRNA | ASO, conf 0.90)
- Predicted mechanism: gof|misfolding
- Rationale: The gain-of-function missense mutation in PCSK9 leads to enhanced LDLR degradation, causing familial hypercholesterolemia. The mutation results in a toxic protein product that misfolds and aggregates, disrupting normal cellular function and contributing to the disease phenotype. Targeting PCSK9 mRNA with siRNA or ASO can effectively reduce LDL-C levels in patients with familia...

### obesity_pomc -- RECOVERED

- Gene: POMC
- Expected target: MC4R
- Predicted target: `MC4R` (Agonist, conf 0.90)
- Predicted mechanism: lof
- Rationale: The POMC mutation leads to the absence of ACTH/MSH peptides, resulting in severe early-onset obesity. The MC4R protein is a downstream effector of POMC, and its agonism can bypass the missing ligand, correcting the disease phenotype. Setmelanotide (Imcivree) is an approved drug that targets MC4R, making it a suitable therapeutic strategy.

### porphyria_alas1 -- RECOVERED

- Gene: HMBS
- Expected target: ALAS1
- Predicted target: `ALAS1` (inhibitor, conf 0.90)
- Predicted mechanism: lof
- Rationale: The mechanism of HMBS loss-of-function leading to ALA/PBG accumulation is mediated by the downstream effector ALAS1. Givosiran (Givlaari) targets ALAS1, inhibiting its activity and reducing ALA/PBG accumulation. This is a classic example of targeting a downstream effector enzyme, which is the correct therapeutic strategy for this disease.

### scd_hbb -- MISS

- Gene: HBB
- Expected target: HBB
- Predicted target: `MYB` (Activator, conf 0.80)
- Predicted mechanism: gof
- Rationale: The mechanism of the HBB mutation is gain-of-function, where the hemoglobin S protein polymerizes under hypoxic conditions. The MYB protein is a transcriptional regulator that controls the expression of the HBB gene. By activating the MYB protein, we can increase the expression of the HBB gene and reduce the polymerization of hemoglobin S. This is consistent with the mechanism...

### sma_smn1 -- RECOVERED

- Gene: SMN1
- Expected target: SMN2
- Predicted target: `SMN1` (inhibitor | activator | chaperone | siRNA | ASO | gene_therapy | crispr | modulator | replacement, conf 0.80)
- Predicted mechanism: lof
- Rationale: The mechanism of SMN1 homozygous deletion of exon 7-8 is lof of an inhibitor whose downstream effector is the symptom driver. The SMN1 gene is not the target, but rather the downstream effector enzyme, which is the SMN protein itself. The precedent drug onasemnogene abeparvovec (Zolgensma) targets the SMN protein, replacing it with a functional copy of the SMN1 gene. This is a...
