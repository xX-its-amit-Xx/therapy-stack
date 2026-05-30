# Full review -- blinded_v20_val_llama.json

## Headline

- Backend: `llama`
- N cases: 12
- Target recovered: 9/12 (75%) -- Wilson 95% CI [47%, 91%]
- Modality recovered: 8/12
- Citation recovered: 0/12
- Full (target+modality+citation): 0/12
- Baseline disease-gene: 8/12
- Baseline 1st interactor: 1/12
- Total wall: 5939.4s (99.0 min)

## Miss taxonomy
## Miss taxonomy -- blinded_v20_val_llama.json (3/12 misses)

| Failure mode | N | Cases |
|---|---|---|
| disease_gene_default | 3 | crinecerfont_cah, iptacopan_pnh, sotatercept_pah |

| Case | Disease gene | Expected | Predicted | Mode |
|---|---|---|---|---|
| `crinecerfont_cah` | CYP21A2 | `CRHR1` | `CYP21A2` | `disease_gene_default` |
| `iptacopan_pnh` | PIGA | `CFB` | `PIGA (mRNA)` | `disease_gene_default` |
| `sotatercept_pah` | BMPR2 | `ACVR2A` | `BMPR2` | `disease_gene_default` |


## Node contribution + token economy
# Node contribution -- blinded_v20_val_llama.json

Cases: 12 total (9 recovered, 3 missed)

## LLM calls per node

| Node | Cases firing | Total calls | Calls on hits | Calls on misses | Avg/case |
|---|---|---|---|---|---|
| `self_critique` | 12/12 (100%) | 12 | 9 | 3 | 1.0 |

## Token economy of failures

- Tokens consumed on hits (9 cases):   in=5852, out=5772
- Tokens consumed on misses (3 cases): in=1892, out=1932
- Per-case in tokens: hits=650, misses=631 (misses spend 0.97x the input)
- Per-case out tokens: hits=641, misses=644


## Calibration
## Calibration -- blinded_v20_val_llama.json (backend=llama, n=12)

| Conf bin | N | Mean conf | Mean accuracy | Gap (conf - acc) |
|---|---|---|---|---|
| [0.00, 0.30) | 1 | 0.20 | 1.00 | -0.80 |
| [0.30, 0.50) | 4 | 0.40 | 0.75 | -0.35 |
| [0.50, 0.70) | 3 | 0.53 | 0.67 | -0.13 |
| [0.70, 0.85) | 4 | 0.73 | 0.75 | -0.02 |
| [0.85, 1.01) | 0 | -- | -- | -- |

**ECE (lower = better):** 0.225
**Brier score (lower = better):** 0.271

> Calibration is poor. The model's confidence is meaningfully decoupled from its accuracy; downstream consumers should NOT use confidence as a trustworthy reliability signal.


## Per-case evidence (HTML)
Per-case evidence: [blinded_v20_val_llama.html](./blinded_v20_val_llama.html)
