# Update_cell_proprity2 Cython Implementation

## Scope

This branch also implements a Cython exact-intent kernel for `river_for_net.Update_cell_proprity2`, but this kernel is not part of the current recommended exact candidate because it still introduces measurable drift.

## Files

- `cython_river_kernels.pyx`
- `build_cython_exact_kernels.py`
- `river_for_net.py`

## Entry Point

- Runtime flag:
  - `ISLAM_USE_CYTHON_UPDATE_CELL=1`
- Python gate:
  - `river._cython_cell_state_ready`
- Python caller:
  - `River.Update_cell_proprity2()`
- Cython entry:
  - `cython_river_kernels.update_cell_properties_exact(river)`

## What Moved To Cython

The outer per-cell state refresh loop now runs in Cython:

1. clamp and refresh cell area
2. query level / depth from the prebound table
3. apply dry / near-dry handling
4. refresh velocity / celerity / Froude
5. refresh wetted perimeter / pressure / hydraulic radius
6. zero `QIN`

## Why It Is Not Yet Accepted

The kernel is fast, but it does not yet reproduce the Python path bit-for-bit.

### 10-Minute Validation Result

- Baseline:
  - `reports/serial_python_10m_noprof_summary.json`
  - evolve/model time: `4.743990 s`
- Candidate:
  - `reports/cython_update_cell_10m_hit_v2b_summary.json`
  - evolve/model time: `1.530594 s`
- Compare:
  - `reports/cython_update_cell_10m_hit_v2b_compare.json`
- Result:
  - `allclose = false`

### Observed Drift

- `cfl_history.csv time`:
  - `max_abs = 6.103515625e-05`
- `river11_interpolated_output.nc Q`:
  - `max_abs = 9.71555709833316e-06`
- `internal_node_history.csv` worst column:
  - `n13_river14_face_Q`
  - `max_abs = 0.0012717474781922533`

## Current Recommendation

Keep this kernel behind its feature flag for continued investigation, but do not include it in the exact candidate baseline until the first source of drift is isolated and fixed.
