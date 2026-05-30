# Dataset diversity

How balanced is the benchmark across target-kinds, modalities,
and therapeutic areas? A split that's 80% oncology is a
different benchmark than one that's spread across 6 areas.

| Split | N | Multi-target cases |
|---|---|---|
| dev | 16 | 3 |
| val | 12 | 10 |
| adversarial | 7 | 7 |

## Split: dev (N=16)

### Target kind

| Value | N | % |
|---|---|---|
| `disease_gene` | 9 | 56% |
| `downstream_effector` | 6 | 38% |
| `paralog` | 1 | 6% |

### Modulation type

| Value | N | % |
|---|---|---|
| `inhibitor` | 9 | 56% |
| `siRNA_ASO` | 3 | 19% |
| `splice_modifier` | 1 | 6% |
| `chaperone` | 1 | 6% |
| `activator` | 1 | 6% |
| `gene_therapy` | 1 | 6% |

### Therapeutic area

| Value | N | % |
|---|---|---|
| `neuro` | 4 | 25% |
| `metabolic` | 3 | 19% |
| `oncology` | 3 | 19% |
| `rare hematology` | 2 | 12% |
| `cardiovascular` | 2 | 12% |
| `other` | 1 | 6% |
| `inflammation` | 1 | 6% |

## Split: val (N=12)

### Target kind

| Value | N | % |
|---|---|---|
| `downstream_effector` | 6 | 50% |
| `disease_gene` | 6 | 50% |

### Modulation type

| Value | N | % |
|---|---|---|
| `inhibitor` | 9 | 75% |
| `activator` | 2 | 17% |
| `antibody` | 1 | 8% |

### Therapeutic area

| Value | N | % |
|---|---|---|
| `cardiovascular` | 2 | 17% |
| `oncology` | 2 | 17% |
| `rare hematology` | 2 | 17% |
| `other` | 2 | 17% |
| `neuro` | 1 | 8% |
| `endocrine` | 1 | 8% |
| `metabolic` | 1 | 8% |
| `inflammation` | 1 | 8% |

## Split: adversarial (N=7)

### Target kind

| Value | N | % |
|---|---|---|
| `downstream_effector` | 4 | 57% |
| `disease_gene` | 3 | 43% |

### Modulation type

| Value | N | % |
|---|---|---|
| `inhibitor` | 2 | 29% |
| `siRNA_ASO` | 2 | 29% |
| `activator` | 1 | 14% |
| `splice_modifier` | 1 | 14% |
| `gene_therapy` | 1 | 14% |

### Therapeutic area

| Value | N | % |
|---|---|---|
| `rare hematology` | 2 | 29% |
| `neuro` | 2 | 29% |
| `metabolic` | 1 | 14% |
| `cardiovascular` | 1 | 14% |
| `other` | 1 | 14% |

## Cross-split: modality coverage gap

- Modalities in dev only: `['chaperone']`
- Modalities in val only: `['antibody']`
- Modalities in adv only: `[]`
- Modalities in all 3:    `['activator', 'inhibitor']`

