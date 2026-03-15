# Cython Error Report

## Measurement Policy

- compare target:
  - single-process pure-Python exact baseline on this branch
- timing headline elsewhere uses evolve/model time only
- initialization is excluded from headline timing

## Validated Exact Kernels

### Nodechain

- 10-minute:
  - `reports/cython_nodechain_10m_noprof_v2_compare.json`
  - `allclose = true`
- 2-hour:
  - `reports/cython_nodechain_2h_noprof_v2_compare.json`
  - `allclose = true`

### Roe Flux

- 10-minute:
  - `reports/cython_roe_flux_10m_hit_v2b_compare.json`
  - `allclose = true`

### Combined Exact Candidate

- flags:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- 10-minute:
  - `reports/cython_nodechain_roe_10m_hit_compare.json`
  - `allclose = true`
- 2-hour:
  - `reports/cython_nodechain_roe_2h_hit_compare.json`
  - `allclose = true`
- 40-hour:
  - `reports/cython_nodechain_roe_40h_exact_compare.json`
  - `allclose = true`
  - worst reported file metric:
    - `internal_node_history.csv:n13_river14_face_Q`
    - `max_abs = 4.547473508864641e-13`

## Kernel With Drift

### Update Cell

- compare:
  - `reports/cython_update_cell_10m_hit_v2b_compare.json`
- result:
  - `allclose = false`
- first actionable drift summary:
  - `cfl_history.csv time max_abs = 6.103515625e-05`
  - `river11_interpolated_output.nc Q max_abs = 9.71555709833316e-06`
  - `internal_node_history.csv` worst column:
    - `n13_river14_face_Q`
    - `max_abs = 0.0012717474781922533`

## Status

- current exact candidate:
  - `nodechain + Roe flux`
- excluded from exact candidate:
  - `Update_cell_proprity2` Cython kernel

## Conclusion

At this point the exact candidate is fully validated on 10-minute, 2-hour, and 40-hour cases, while the update-cell kernel remains the only Cython hotspot implementation that still shows measurable drift.
