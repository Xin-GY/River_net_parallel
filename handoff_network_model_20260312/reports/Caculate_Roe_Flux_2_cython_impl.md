# Caculate_Roe_Flux_2 Cython Implementation

## Scope

This branch adds an exact Cython batch path for the general-HR portion of `river_for_net.Caculate_Roe_Flux_2`.

## Files

- `cython_river_kernels.pyx`
- `build_cython_exact_kernels.py`
- `river_for_net.py`

## Entry Point

- Runtime flag:
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
- Python gate:
  - `river._general_hr_cython_batch_ready`
- Python caller:
  - `River._caculate_roe_flux_general_hr()`
- Cython entry:
  - `cython_river_kernels.fill_general_hr_flux_exact(river)`

## What Moved To Cython

The exact outer per-face loop for the general-HR Roe flux path now runs in Cython.

Moved work:

1. iterate over all interfaces `i = 0 .. cell_num`
2. read prebound left/right section tables
3. call exact interface flux evaluation
4. apply positivity flux control in the same serial order
5. write `Flux_LOC`
6. write `Flux_Source_left/right`
7. apply rainfall source contribution per cell

## Prebinding

At river initialization / section-view refresh time, Python now prebinds:

- `_general_hr_left_tables`
- `_general_hr_right_tables`
- `_general_hr_cython_batch_ready`

This avoids hot-path:

- section-name string lookup
- table dict lookup
- Python-side per-interface object assembly

## Exactness Rules

- exact interface computation still goes through the accepted Cython cross-section implementation:
  - `cython_cross_section.compute_general_hr_flux_interface`
- same positivity limiter logic
- same source-term write order
- no parallelism
- no float32 substitution for the interface flux arithmetic

## Validation

### 10-Minute Roe-Only Run

- Baseline:
  - `reports/serial_python_10m_noprof_summary.json`
  - evolve/model time: `4.743990 s`
- Candidate:
  - `reports/cython_roe_flux_10m_hit_v2b_summary.json`
  - evolve/model time: `1.635677 s`
- Compare:
  - `reports/cython_roe_flux_10m_hit_v2b_compare.json`
- Result:
  - `allclose = true`
  - control points: exact
  - final state: exact

### Combined Exact Candidate With Nodechain

- Candidate:
  - `reports/cython_nodechain_roe_10m_hit_summary.json`
  - evolve/model time: `1.451734 s`
- Compare:
  - `reports/cython_nodechain_roe_10m_hit_compare.json`
- Result:
  - `allclose = true`

## Conclusion

`Caculate_Roe_Flux_2` is the first large serial hotspot where Cythonizing the outer loop delivers a major exact speedup. This kernel is part of the current best exact candidate on this branch.
