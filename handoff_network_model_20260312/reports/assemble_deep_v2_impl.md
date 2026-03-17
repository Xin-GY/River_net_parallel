# Assemble Deep V2 Implementation

## Files Touched

- `handoff_network_model_20260312/river_for_net.py`
- `handoff_network_model_20260312/cython_river_kernels.pyx`
- `handoff_network_model_20260312/cpp/river_kernels.hpp`
- `handoff_network_model_20260312/cpp/river_kernels.cpp`
- `handoff_network_model_20260312/tools/profile_cpp_exact_serial.py`

## What Changed

### Python Routing

`River.Assemble_Flux_2()` now checks `ISLAM_CPP_USE_ASSEMBLE_DEEP=1` first. If the deep Cython/C++ path succeeds, it returns immediately and skips the old Python conservative increment + native poststep split path.

### Cython Bridge

Added `assemble_flux_exact_deep_cpp()`:

- binds `Flux_LOC`
- binds source/friction arrays
- binds `Flux`
- binds `S/Q`
- binds `water_depth`
- binds `cell_s_limit`
- binds `forced_dry_recorded`
- binds `cell_lengths`
- reuses the prebuilt update-cell table plan

### C++ Kernel

Added `rivernet::assemble_flux_exact_deep(...)`:

1. computes per-cell conservative flux increment directly from left/right face storage
2. writes `Flux[cell, 0/1]`
3. updates `S/Q` in place using the same `DT / cell_length` ordering
4. runs the same Manning post-step logic
5. runs the same conservative dry admissibility pass

The kernel intentionally stops there; derived-state refresh still belongs to the existing accepted update-cell path.

### Benchmark Wiring

Added `--use-cpp-assemble-deep` to `tools/profile_cpp_exact_serial.py`, exporting `ISLAM_CPP_USE_ASSEMBLE_DEEP`.

## What Was Explicitly Not Changed

- no nodechain modifications
- no refresh-deep logic
- no fullstep/dispatch reshaping
- no external-boundary-deep code
- no C++ threads
