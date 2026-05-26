# Per-case results — full e2e run

**Model:** `Llama-3.2-3B-Instruct-Q4_K_M.gguf` (Q4_K_M, llama-cpp-python, CPU)  
**Retriever:** UniProt REST  
**Cases:** 10 real FDA approvals from `fda-strategy-triples` v0.1.0  
**Recovered:** 8 / 10  
**Mean rank of correct target:** 1.62

| # | Drug | Disease gene(s) | Gold target | Top-1 prediction | Rank | Recovered |
|---|---|---|---|---|---|---|
| 1 | Spinraza | SMN1, SMN2 | SMN2 pre-mRNA intron 7 intronic splicing silencer ISS-N1 (no UniProt; RNA target) | `SMN2` | 1 | YES |
| 2 | Zolgensma | SMN1 | SMN1 locus (transgene delivered via AAV9 capsid; no UniProt target — gene addition therap... | `SMN1` | 1 | YES |
| 3 | Kalydeco | CFTR | P13569 (CFTR) — ATP-binding cassette transporter subfamily C member 7 | `CFTR (gene)` | 1 | YES |
| 4 | Galafold | GLA | P06280 (GLA) — alpha-galactosidase A (lysosomal) | `GLA (mRNA)` | 1 | YES |
| 5 | Zokinvy | LMNA | Q14192 (FNTB) — farnesyltransferase subunit beta; prevents farnesylation of progerin C-te... | `SREBF1` | - | NO |
| 6 | Amvuttra | TTR | P02766 (TTR) — transthyretin mRNA (hepatic); drug reduces circulating TTR protein | `STT3B` | - | NO |
| 7 | Givlaari | HMBS, CPOX, PPOX, ALAS1 | P13196 (ALAS1) — delta-aminolevulinic acid synthase 1 mRNA (hepatic) | `CPOX` | 2 | YES |
| 8 | Evrysdi | SMN1, SMN2 | SMN2 pre-mRNA — drug stabilises the 5' splice site of exon 7 by interacting with U1-snRNP... | `SMN1` | 2 | YES |
| 9 | Casgevy | BCL11A, HBB | BCL11A erythroid enhancer (chr2:60,495,250-60,495,390 hg38) — transcriptional repressor o... | `MTA2` | 3 | YES |
| 10 | Leqvio | PCSK9, LDLR | P53779 (PCSK9) — proprotein convertase subtilisin/kexin type 9 mRNA (hepatic); GalNAc-con... | `LDLR` | 2 | YES |

## Per-case strategy traces

### Spinraza (ASO) — + RECOVERED

**Disease:** Spinal muscular atrophy (SMA), types 1–4
**Disease gene(s):** SMN1, SMN2
**Gold target:** SMN2 pre-mRNA intron 7 intronic splicing silencer ISS-N1 (no UniProt; RNA target)
**Elapsed:** 31.2s

1. `SMN2` [gene_therapy] c=0.80  
   SMN2 is the only functional copy of the SMN1 gene in individuals with SMA, and increasing its expression can compensate for the loss of SMN1 function. Gene therapy can be used to deliver a functional copy of SMN2 to pat...
2. `GEMIN4` [siRNA] c=0.70  
   GEMIN4 is a component of the SMN complex and is required for the assembly of the core snRNP. Knocking down GEMIN4 can reduce the activity of the SMN complex and alleviate SMA symptoms.
3. `STRAP/UNRIP` [small_molecule] c=0.60  
   STRAP/UNRIP is a component of the SMN complex and is required for the assembly of the core snRNP. Inhibiting STRAP/UNRIP can reduce the activity of the SMN complex and alleviate SMA symptoms.

### Zolgensma (gene_therapy) — + RECOVERED

**Disease:** Spinal muscular atrophy (SMA) with biallelic SMN1 mutations in patients <2 years
**Disease gene(s):** SMN1
**Gold target:** SMN1 locus (transgene delivered via AAV9 capsid; no UniProt target — gene addition therapy)
**Elapsed:** 18.2s

1. `SMN1` [protein_replacement] c=0.80  
   Replace the deficient SMN1 protein with a functional copy to restore the SMN complex and improve splicing of pre-mRNAs.
2. `GEMIN2/SIP1` [small_molecule] c=0.70  
   Inhibit GEMIN2/SIP1, a key component of the SMN complex, to reduce its interaction with SMN1 and restore the assembly of the core snRNP.
3. `DDX20/GEMIN3` [small_molecule] c=0.60  
   Block DDX20/GEMIN3, a component of the SMN complex, to reduce its interaction with SMN1 and restore the assembly of the core snRNP.

### Kalydeco (modulator) — + RECOVERED

**Disease:** Cystic fibrosis (CF) with CFTR gating mutations (G551D and other class III/IV variants)
**Disease gene(s):** CFTR
**Gold target:** P13569 (CFTR) — ATP-binding cassette transporter subfamily C member 7
**Elapsed:** 14.4s

1. `CFTR (gene)` [gene_therapy] c=0.80  
   Correct the CFTR gene mutation by replacing the defective gene with a healthy copy, restoring normal CFTR protein function.
2. `GOPC (PDZ domain)` [small_molecule] c=0.70  
   Block GOPC's interaction with CFTR, preventing CFTR internalization and restoring channel activity.
3. `PKA` [ASO] c=0.60  
   Inhibit PKA phosphorylation of CFTR, reducing channel activation and ATPase activity.

### Galafold (chaperone) — + RECOVERED

**Disease:** Fabry disease with amenable GLA variants
**Disease gene(s):** GLA
**Gold target:** P06280 (GLA) — alpha-galactosidase A (lysosomal)
**Elapsed:** 15.9s

1. `GLA (mRNA)` [gene_therapy] c=0.80  
   Directly replace the faulty GLA gene with a healthy copy to restore normal N-acetyltransferase 8 function, thereby correcting the underlying molecular mechanism of Fabry disease.
2. `PROM1` [small_molecule] c=0.60  
   Target the acetyl-CoA-dependent N-acetyltransferase activity of GLA to regulate apoptosis and amyloid beta-peptide secretion, thereby compensating for the loss of function caused by the GLA variants.
3. `BACE1` [ASO] c=0.50  
   Block the acetyl-CoA-dependent N-acetyltransferase activity of GLA to regulate amyloid beta-peptide secretion, thereby mitigating the pathology of Fabry disease.

### Zokinvy (inhibitor) — - MISS

**Disease:** Hutchinson-Gilford Progeria Syndrome (HGPS) and processing-deficient progeroid laminopathies
**Disease gene(s):** LMNA
**Gold target:** Q14192 (FNTB) — farnesyltransferase subunit beta; prevents farnesylation of progerin C-terminal CAAX motif
**Elapsed:** 19.8s

1. `SREBF1` [small_molecule] c=0.80  
   Blocking SREBF1 would reduce the expression of prelamin-A/C, thereby mitigating its pro-senescence effects on vascular smooth muscle cells. This approach targets the upstream regulator of prelamin-A/C, rather than the p...
2. `EMD` [protein_replacement] c=0.70  
   Replacing EMD with a functional homolog could restore the interaction with lamin A/C, potentially stabilizing the nuclear lamina and reducing the effects of prelamin-A/C. This approach targets the interaction partner of...
3. `LMNA (mRNA)` [gene_therapy] c=0.60  
   Targeting the LMNA mRNA directly could reduce the expression of prelamin-A/C, thereby mitigating its effects on vascular smooth muscle cells. This approach targets the gene responsible for the disease protein, rather th...

### Amvuttra (siRNA) — - MISS

**Disease:** Hereditary transthyretin-mediated amyloidosis (hATTR) with polyneuropathy in adults
**Disease gene(s):** TTR
**Gold target:** P02766 (TTR) — transthyretin mRNA (hepatic); drug reduces circulating TTR protein
**Elapsed:** 17.2s

1. `STT3B` [small_molecule] c=0.80  
   Targeting the enzyme responsible for glycosylation of TTR, STT3B, could prevent the formation of amyloidogenic variants, thereby addressing the underlying molecular mechanism of hATTR.
2. `RBP4` [antibody] c=0.60  
   Blocking the interaction between TTR and RBP4 could prevent the formation of amyloid fibrils, as RBP4 is thought to play a role in stabilizing the native conformation of TTR.
3. `AMYLD1` [gene_therapy] c=0.40  
   Gene therapy targeting the AMYLD1 gene could potentially prevent the formation of amyloidogenic variants of TTR, thereby addressing the underlying molecular mechanism of hATTR.

### Givlaari (siRNA) — + RECOVERED

**Disease:** Acute hepatic porphyria (AHP), including acute intermittent porphyria (AIP), hereditary coproporphyria (HCP), variegate porphyria (VP)
**Disease gene(s):** HMBS, CPOX, PPOX, ALAS1
**Gold target:** P13196 (ALAS1) — delta-aminolevulinic acid synthase 1 mRNA (hepatic)
**Elapsed:** 30.7s

1. `CPOX` [ASO] c=0.80  
   Targeting CPOX reduces the accumulation of coproporphyrinogen-III, which is toxic to cells and contributes to the pathology of AHP. By knocking down CPOX mRNA, we can decrease the levels of toxic intermediates in the he...
2. `ALAS1` [gene_therapy] c=0.70  
   Increasing ALAS1 expression can compensate for the reduced activity of HMBS, the enzyme responsible for the first step in heme biosynthesis. This can help to restore normal levels of heme and reduce the accumulation of ...
3. `HMBS` [protein_replacement] c=0.90  
   Replacing HMBS with a functional enzyme can directly address the underlying molecular mechanism of AHP. This approach can be particularly effective if the HMBS protein is not toxic or if its toxicity can be mitigated.

### Evrysdi (modulator) — + RECOVERED

**Disease:** Spinal muscular atrophy (SMA), types 1–3 and presymptomatic
**Disease gene(s):** SMN1, SMN2
**Gold target:** SMN2 pre-mRNA — drug stabilises the 5' splice site of exon 7 by interacting with U1-snRNP and SRSF1 splicing factors (RNA target, no UniProt accession)
**Elapsed:** 20.3s

1. `SMN1` [gene_therapy] c=0.80  
   Restore SMN1 expression to compensate for the lack of functional SMN1 protein in SMA patients.
2. `SMN2` [ASO] c=0.70  
   Inhibit SMN2 mRNA to reduce its production and increase the production of functional SMN1 protein.
3. `GEMIN4` [siRNA] c=0.60  
   Knockdown GEMIN4, which is essential for the assembly of the SMN complex, to reduce the production of toxic SMN1 protein.

### Casgevy (gene_therapy) — + RECOVERED

**Disease:** Sickle cell disease (SCD) in patients ≥12 years; transfusion-dependent beta-thalassemia (TDT, approved 2024-01-16)
**Disease gene(s):** BCL11A, HBB
**Gold target:** BCL11A erythroid enhancer (chr2:60,495,250-60,495,390 hg38) — transcriptional repressor of fetal hemoglobin (no UniProt; regulatory DNA target)
**Elapsed:** 22.3s

1. `MTA2` [small_molecule] c=0.80  
   MTA2 is a component of the NuRD repressor complex that interacts with BCL11A, and its inhibition may reduce BCL11A-mediated repression of HBG1, leading to increased fetal hemoglobin levels.
2. `NR2F1` [antibody] c=0.60  
   NR2F1 is a transcription factor that interacts with BCL11A and may regulate its activity. Blocking NR2F1 may reduce BCL11A-mediated repression of HBG1.
3. `BCL11A` [gene_therapy] c=0.40  
   BCL11A is a transcription factor that regulates the developmental switch from gamma- to beta-globin. Directly targeting BCL11A via gene therapy may restore normal globin expression.

### Leqvio (siRNA) — + RECOVERED

**Disease:** Heterozygous familial hypercholesterolemia (HeFH) and clinical atherosclerotic cardiovascular disease (ASCVD) requiring additional LDL-C lowering
**Disease gene(s):** PCSK9, LDLR
**Gold target:** P53779 (PCSK9) — proprotein convertase subtilisin/kexin type 9 mRNA (hepatic); GalNAc-conjugate delivered to hepatocytes via ASGR1
**Elapsed:** 20.1s

1. `LDLR` [small_molecule] c=0.80  
   Blocking the interaction between PCSK9 and LDLR could increase LDLR-mediated LDL internalization, reducing PCSK9's pro-cholesterolemic effects.
2. `PCSK9` [gene_therapy] c=0.90  
   Correcting the genetic defect that leads to PCSK9 overproduction could normalize LDLR degradation and lower cholesterol levels.
3. `MYLIP` [small_molecule] c=0.70  
   Inhibiting MYLIP's ubiquitination activity could reduce PCSK9 degradation and increase its activity, leading to increased LDLR degradation and lower cholesterol levels.
