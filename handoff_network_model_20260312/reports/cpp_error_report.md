# C++ Evolve Bridge Error Report

## Scope

This report validates the current `cpp bridge` path against the same-branch single-process exact serial route, using explicit exact kernel flags:

- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_USE_CYTHON_UPDATE_CELL=0`

The bridge route adds:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`

## Root Cause Found During Validation

The first bridge draft introduced small long-run drift because the Cython bridge converted per-step time values through `float(...)` on every iteration. That changed the exact scalar update path enough to show up after 2 hours.

The bridge was corrected to preserve the original Python-object arithmetic order for:

- `current_sim_time`
- `DT`
- `sub_step_time`
- CFL/yield-step boundary checks

After that change, the exact compare returned to fully clean.

## 10-Minute Compare

- baseline:
  - `result/cython_exact_serial_10m_recheck`
- candidate:
  - `result/cpp_evolve_serial_10m_explicitkernels`
- report:
  - `reports/cpp_bridge_explicitkernels_vs_cython_serial_10m.json`
- result:
  - `allclose = true`

## 2-Hour Compare

- baseline:
  - `result/cython_exact_serial_2h_recheck`
- candidate:
  - `result/cpp_evolve_serial_2h_explicitkernels_v2`
- report:
  - `reports/cpp_bridge_explicitkernels_vs_cython_serial_2h_v2.json`
- result:
  - `allclose = true`

## 40-Hour Compare

- baseline:
  - `result/cython_exact_serial_40h_recheck`
- candidate:
  - `result/cpp_evolve_serial_40h_explicitkernels_v1`
- report:
  - `reports/cpp_bridge_explicitkernels_vs_cython_serial_40h.json`
- result:
  - `allclose = true`

## Notes On Accepted-Baseline Compare

Direct directory compare against the historical accepted 40-hour output tree is not a clean gate for this branch because the saved output cadence differs, especially in `internal_node_history.csv` row counts.

For exactness on this branch, the correct gate is:

- same branch
- same kernel set
- same output schedule
- only toggle `ISLAM_USE_CPP_EVOLVE`

Under that gate, the bridge is currently exact.
