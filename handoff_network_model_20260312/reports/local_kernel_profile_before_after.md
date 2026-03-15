# Local Kernel Profile Before/After

## Measurement Policy

- single-process only
- evolve/model time only
- initialization excluded

## Baseline Serial Python

- 10-minute:
  - `reports/serial_python_10m_noprof_summary.json`
  - evolve/model time: `4.743990 s`
- 2-hour:
  - `reports/serial_python_2h_noprof_summary.json`
  - evolve/model time: `35.700089 s`

## Nodechain Only

- 10-minute:
  - `reports/cython_nodechain_10m_noprof_v2_summary.json`
  - evolve/model time: `4.591877 s`
  - speedup vs baseline: `1.033x`
- 2-hour:
  - `reports/cython_nodechain_2h_noprof_v2_summary.json`
  - evolve/model time: `34.740252 s`
  - speedup vs baseline: `1.028x`

## Roe Flux Only

- 10-minute:
  - `reports/cython_roe_flux_10m_hit_v2b_summary.json`
  - evolve/model time: `1.635677 s`
  - speedup vs baseline: `2.900x`
- correctness:
  - `reports/cython_roe_flux_10m_hit_v2b_compare.json`
  - `allclose = true`

## Update Cell Only

- 10-minute:
  - `reports/cython_update_cell_10m_hit_v2b_summary.json`
  - evolve/model time: `1.530594 s`
  - speedup vs baseline: `3.099x`
- correctness:
  - `reports/cython_update_cell_10m_hit_v2b_compare.json`
  - `allclose = false`

## Best Current Exact Candidate

- flags:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- 10-minute:
  - `reports/cython_nodechain_roe_10m_hit_summary.json`
  - evolve/model time: `1.451734 s`
  - speedup vs baseline: `3.268x`
- 2-hour:
  - `reports/cython_nodechain_roe_2h_hit_summary.json`
  - evolve/model time: `11.496324 s`
  - speedup vs baseline: `3.105x`
- 40-hour:
  - `reports/cython_nodechain_roe_40h_exact_summary.json`
  - evolve/model time: `213.933772 s`
  - speedup vs baseline: `2.628x`
- correctness:
  - `reports/cython_nodechain_roe_10m_hit_compare.json`
  - `reports/cython_nodechain_roe_2h_hit_compare.json`
  - `reports/cython_nodechain_roe_40h_exact_compare.json`
  - all validated compares are `allclose = true`

## Interpretation

The large single-process gain is coming overwhelmingly from the Roe-flux outer-loop Cythonization. The nodechain Cythonization is exact and useful, but its standalone speedup is modest. The update-cell kernel is promising for speed, but it still needs numerical debugging before it can join the exact candidate.

## 2-Hour Profile Share Shift

Profile source:

- before:
  - `reports/serial_python_2h_loop_only_profile_summary.json`
- after:
  - `reports/cython_nodechain_roe_2h_profile_hit_v3_profile_summary.json`

Measured against profiled evolve-loop wall:

| Function | Before Cumtime (s) | Before Share | After Cumtime (s) | After Share |
|---|---:|---:|---:|---:|
| `Update_boundary_conditions` | 48.245624 | 59.13% | 9.428808 | 40.71% |
| `Update_internal_boundary_conditions` | 45.519832 | 55.78% | 7.779284 | 33.59% |
| `Caculate_Roe_Flux_2` | 13.577339 | 16.64% | 3.950099 | 17.06% |
| `Update_cell_proprity2` | 9.886540 | 12.12% | 3.602109 | 15.55% |
| `Assemble_Flux_2` | 6.804679 | 8.34% | 3.178756 | 13.72% |
| `_refresh_cell_state` | 17.014079 | 20.85% | 5.976743 | 25.81% |

Additional after-only visibility:

- `_stage_boundary_fix_level_cython_fast`:
  - `7.131580 s`
  - `30.79%` of profiled evolve loop

This confirms the accepted exact candidate has already removed a large amount of Python overhead, and that the next exact frontier is now the remaining per-cell update / assemble / refresh chain rather than the nodechain shell alone.
