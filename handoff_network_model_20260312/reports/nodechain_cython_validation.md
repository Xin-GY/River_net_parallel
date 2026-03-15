# Nodechain Cython Validation

## Validation Policy

- compare target:
  - single-process pure-Python exact baseline on this branch
- timing headline:
  - evolve/model time only
- initialization is excluded from headline timing

## 10-Minute Case

- Baseline summary:
  - `reports/serial_python_10m_noprof_summary.json`
  - evolve/model time: `4.743990 s`
- Candidate summary:
  - `reports/cython_nodechain_10m_noprof_v2_summary.json`
  - evolve/model time: `4.591877 s`
- Compare:
  - `reports/cython_nodechain_10m_noprof_v2_compare.json`
- Result:
  - `allclose = true`
  - control points: exact
  - final state: exact
  - first drift: none

## 2-Hour Case

- Baseline summary:
  - `reports/serial_python_2h_noprof_summary.json`
  - evolve/model time: `35.700089 s`
- Candidate summary:
  - `reports/cython_nodechain_2h_noprof_v2_summary.json`
  - evolve/model time: `34.740252 s`
- Compare:
  - `reports/cython_nodechain_2h_noprof_v2_compare.json`
- Result:
  - `allclose = true`
  - control points: exact
  - final state: exact
  - first drift: none

## Conclusion

The nodechain Cython path is exact for the cases validated so far and gives a modest standalone speedup:

- 10-minute evolve/model speedup:
  - `4.743990 / 4.591877 = 1.033x`
- 2-hour evolve/model speedup:
  - `35.700089 / 34.740252 = 1.028x`

This confirms the Cython nodechain shell is safe, but also shows that most of the large serial gain has to come from the river-side kernels, not from nodechain alone.

## 40-Hour Combined Exact Candidate

The branch-level exact candidate combines the validated nodechain kernel with the validated Roe-flux kernel:

- flags:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- summary:
  - `reports/cython_nodechain_roe_40h_exact_summary.json`
  - evolve/model time: `213.933772 s`
- compare:
  - `reports/cython_nodechain_roe_40h_exact_compare.json`
- result:
  - `allclose = true`
  - control points: exact within compare tolerance
  - final state: exact
  - worst reported file metric:
    - `internal_node_history.csv:n13_river14_face_Q`
    - `max_abs = 4.547473508864641e-13`
