## Files changed

- `cpp/river_kernels.hpp`
- `cpp/river_kernels.cpp`
- `cython_river_kernels.pyx`
- `river_for_net.py`
- `tools/profile_cpp_exact_serial.py`

## Implementation

### 1. Persistent native face plan

Added `CppGeneralHrFluxPlan` in `cython_river_kernels.pyx`.

It prebinds, for every interface:

- left `TableView`
- right `TableView`

This removes per-face lookup through Python tuples during the hot loop.

### 2. Deep exact general-HR kernel

Added `rivernet::fill_general_hr_flux_exact_deep(...)` in `cpp/river_kernels.cpp`.

This kernel now owns the exact per-face loop and directly computes:

- HR-reconstructed interface areas
- interface pressure
- Roe/HLL-like flux branch logic
- positivity flux control
- pressure source corrections
- rain source terms

The kernel consumes contiguous arrays for:

- `river_bed_height`
- `water_depth`
- `S`
- `Q`
- `PRESS`
- `QIN`
- `cell_lengths`

and writes directly into:

- `Flux_LOC`
- `Flux_Source_left`
- `Flux_Source_right`

### 3. River wiring

In `river_for_net.py`:

- added `self.use_cpp_roe_flux_deep`
- added `_cpp_general_hr_flux_plan` and `_cpp_general_hr_flux_ready`
- prepare plan in `_rebind_runtime_section_views()`
- in `_caculate_roe_flux_general_hr()`:
  - first try deep native path
  - otherwise fall back to existing accepted Cython path

### 4. Benchmark wiring

Added `--use-cpp-roe-flux-deep` to `tools/profile_cpp_exact_serial.py` so this path can be benchmarked and bisected independently.

## Exactness notes

This path intentionally keeps:

- same interface traversal order
- same `tiny` resolution
- same Roe entropy fix formula
- same positivity donor and scaling sequence
- same rain source placement

The older accepted path remains available as fallback and comparison anchor.
