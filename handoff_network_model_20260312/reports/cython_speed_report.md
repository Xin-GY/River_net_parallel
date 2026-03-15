# Cython Speed Report

## Measurement Policy

- single-process only
- headline numbers use evolve/model time
- initialization, Fine interpolation, and section-table build are excluded

## Serial Python Baseline

| Case | Summary | Evolve/Model Time (s) | Evolve Wall (s) |
|---|---|---:|---:|
| 10m | `reports/serial_python_10m_noprof_summary.json` | 4.743990 | 4.818651 |
| 2h | `reports/serial_python_2h_noprof_summary.json` | 35.700089 | 35.925078 |
| 40h | `reports/serial_python_40h_noprof_summary.json` | 562.262618 | 565.037927 |

## Exact Cython Candidates

| Candidate | Case | Summary | Evolve/Model Time (s) | Speedup vs Serial Python |
|---|---|---|---:|---:|
| nodechain only | 10m | `reports/cython_nodechain_10m_noprof_v2_summary.json` | 4.591877 | 1.033x |
| nodechain only | 2h | `reports/cython_nodechain_2h_noprof_v2_summary.json` | 34.740252 | 1.028x |
| Roe only | 10m | `reports/cython_roe_flux_10m_hit_v2b_summary.json` | 1.635677 | 2.900x |
| update-cell only | 10m | `reports/cython_update_cell_10m_hit_v2b_summary.json` | 1.530594 | 3.099x |
| nodechain + Roe | 10m | `reports/cython_nodechain_roe_10m_hit_summary.json` | 1.451734 | 3.268x |
| nodechain + Roe | 2h | `reports/cython_nodechain_roe_2h_hit_summary.json` | 11.496324 | 3.105x |
| nodechain + Roe | 40h | `reports/cython_nodechain_roe_40h_exact_summary.json` | 213.933772 | 2.628x |

## Interpretation

- the dominant exact serial speedup comes from the Roe-flux batch kernel
- the nodechain kernel is exact and useful, but only a small standalone gain
- the update-cell kernel is fast but not yet numerically acceptable for the exact line

## Current Best Exact Candidate

- flags:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- 40-hour evolve/model speedup:
  - `562.262618 / 213.933772 = 2.628x`
- 40-hour evolve wall speedup:
  - `565.037927 / 217.559511 = 2.597x`
- step count:
  - unchanged at `29783`

This shows the current win is overwhelmingly single-step cost reduction rather than any change in step count, which is exactly what this branch set out to test.
