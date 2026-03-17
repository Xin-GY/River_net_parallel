# C++ After Global CFL Error Report

## Scope

Candidate under validation:

- accepted exact checkpoint `9a7c094`
- plus `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`

Baseline for exact compare:

- `/tmp/feature_cpp_exact_accepted_reaudit_next/handoff_network_model_20260312/result/accepted_reaudit_rectdeep_{10m,2h,40h}`

## Compare Results

| Case | Compare report | allclose | `cfl_history.csv` | `internal_node_history.csv` | First diff |
| --- | --- | --- | --- | --- | --- |
| 10m | `reports/global_cfl_deep_10m_compare.json` | `true` | `182 == 182` | `181 == 181` | none |
| 2h | `reports/global_cfl_deep_2h_compare.json` | `true` | `1483 == 1483` | `1482 == 1482` | none |
| 40h | `reports/global_cfl_deep_40h_compare.json` | `true` | `29784 == 29784` | `29783 == 29783` | none |

## Key Exactness Result

The deep global-CFL path is exact on all three gate cases:

- 10m
- 2h
- 40h

No drift was observed in:

- `cfl_history.csv`
- `internal_node_history.csv`
- saved river outputs
- final state and control-point files included by `compare_results.py`

The most exact-sensitive field in this round was:

- `cfl_history.csv:global_dt`

and its 40h max abs diff remained:

- `0.0`
