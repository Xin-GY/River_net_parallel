# C++ Rectangular Roe Flux Deep Implementation

## Code Changes

### Native kernel

Added a dedicated exact rectangular flux kernel in:

- `cpp/river_kernels.hpp`
- `cpp/river_kernels.cpp`

New entry point:

- `rivernet::fill_rectangular_hr_flux_exact_deep(...)`

It owns the full rectangular-HR flux stage for the accepted path:

- array zeroing
- center-state load
- hydrostatic reconstruction
- exact Roe solve
- pressure correction write-back
- rain-source write-back

### Cython bridge

Added a direct wrapper in:

- `cython_river_kernels.pyx`

New wrapper:

- `fill_rectangular_hr_flux_exact_cpp_deep(river)`

Guard rails:

- returns `False` if:
  - rectangular HR is not active
  - rectangular width is unavailable
  - explicit TVD limiter is active

### Python route switch

In `river_for_net.py`:

- import the new wrapper
- add env-backed flag:
  - `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP`
- make `_caculate_roe_flux_rectangular_hr()` try the native path first
- keep the old Python path untouched as fallback

### Benchmark harness

In `tools/profile_cpp_exact_serial.py`:

- added `--use-cpp-roe-flux-rect-deep`
- recorded the flag in the summary json

## Why This Is A Real Ownership Push

Before this change, rectangular Roe flux still ran like this:

- Python stage entry
- Python per-face loop
- Python dict state objects
- Python helper chain for load/project/solve/write-back

After this change, the accepted path becomes:

- Python stage entry
- one Cython bridge call
- native per-face loop
- native state ownership and write-back

So the gain comes from removing the Python per-face ownership, not from reshaping dispatch.

## What Was Intentionally Left Alone

- explicit TVD limiter path
- general-HR deep flux path
- nodechain
- build flags
- dispatch shape

This keeps the change narrow and auditable.
