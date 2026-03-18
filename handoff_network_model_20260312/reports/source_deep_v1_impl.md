# Source Deep V1 Implementation

## Code Changes

### `river_for_net.py`

- Added a new environment flag:
  - `ISLAM_CPP_USE_SOURCE_DEEP`
- Added source-plan cache fields:
  - `_cpp_source_plan`
  - `_cpp_source_ready`
- Rebuilds the source plan alongside the accepted cached table state.
- `Caculate_source_term_2()` now tries the native exact path first and falls back to the original Python loop if the flag is off or the plan cannot be prepared.

### `cython_river_kernels.pyx`

- Added `prepare_cpp_source_plan(river)`.
- Added `source_term_exact_deep_cpp(river)`.
- Reused the accepted `CppGeneralHrFluxPlan` shape so the source stage can walk pre-resolved left/right `TableView` arrays without Python section-name lookup.
- Returned friction-clip increments back to the river object.

### `cpp/river_kernels.hpp`

- Added `SourceTermStats`.
- Declared `compute_source_term_exact(...)`.

### `cpp/river_kernels.cpp`

- Added `compute_source_term_exact(...)`.
- The kernel preserves the accepted Python formula sequence:
  - same interface order
  - same `sd/sg/qd/qg` averaging
  - same `friction_min_depth` short-circuit
  - same DEB interpolation threshold `abs(sd - sg) > 0.001`
  - same denominator clip against `EPSILON`
  - same `friction_source[i, 0/1]` assignments

### `tools/profile_cpp_exact_serial.py`

- Added `--use-cpp-source-deep`.
- Exported `ISLAM_CPP_USE_SOURCE_DEEP` into the profiling environment.

## Important Non-Changes

- No grouped evaluator batching
- No boundary ownership changes
- No update-cell / assemble fusion
- No thread path
- No formula changes in `river_for_net.py`

## Environment Note

This machine still lacked a working `h5netcdf` install during the round, so the exact gate used a local no-`h5netcdf` runner and compare helper with the same strict tolerances (`1e-12` / `1e-12`).
