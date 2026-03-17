# C++ Accepted Reaudit Error Report

## Scope

Candidate under validation:

- accepted exact checkpoint `9535623`
- plus `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

Baseline for exact compare:

- `/tmp/feature_cpp_exact_evolve_nodecommit_refresh/handoff_network_model_20260312/result/cpp_nodecommit_deepcommit_{10m,2h,40h}`

## Compare Results

| Case | Compare report | allclose | max_abs | max_rel |
| --- | --- | --- | ---: | ---: |
| 10m | `reports/accepted_reaudit_rectdeep_10m_compare.json` | `true` | `0.0` | `0.0` |
| 2h | `reports/accepted_reaudit_rectdeep_2h_compare.json` | `true` | `0.0` | `0.0` |
| 40h | `reports/accepted_reaudit_rectdeep_40h_compare.json` | `true` | `0.0` | `0.0` |

## Result

The new rectangular Roe-flux deep path is exact on all three gate cases:

- 10m
- 2h
- 40h

No drift was observed in:

- `cfl_history.csv`
- `internal_node_history.csv`
- saved river outputs
- final state and control-point files included by `compare_results.py`

## Interpretation

This round did not introduce a “short-case fast but long-case drift” problem. The path is exact and safe to consider for accepted status.
