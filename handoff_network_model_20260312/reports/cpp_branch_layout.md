# C++ Kernelize-Next Branch Layout

## New Working Line

- branch: `feature/cpp-exact-evolve-kernelize-next`
- worktree: `/tmp/feature_cpp_exact_evolve_kernelize_next`
- start commit: `835cf1f`
- source branch: `feature/cpp-exact-evolve-fullchain`

## Preservation Status

- the source worktree `/tmp/feature_cpp_exact_evolve_fullchain` is intentionally left untouched
- its untracked items remain recoverable in place
- no reset, checkout overwrite, or artifact cleanup was performed before creating this worktree

## Code And Reports Carried Forward

- `cython_cpp_bridge.pyx`
- `build_cpp_exact_kernels.py`
- `cpp/output_buffer.*`
- `cpp/evolve_core.*`
- `Rivernet.py`
- `river_for_net.py`
- `Islam.py`
- current accepted bridge validation reports:
  - `reports/cpp_speed_report.md`
  - `reports/cpp_error_report.md`
  - 10m / 2h / 40h exact compare JSON

## Explicitly Excluded From Formal Commits On This New Line

These may still exist in the old worktree, but they are not part of the new clean line unless explicitly re-added later:

- generated C/C++ build outputs:
  - `cython_cpp_bridge.cpp`
  - `cython_*.c`
  - `*.so`
- superseded exploratory benchmark summaries
- compare reports that came from mismatched output cadence
- FAST / process-pool / adaptive / response-table experiment outputs

## Working Rule For This Branch

- single-process only
- exact only
- evolve/model time only
- no FAST mode
- no process or thread benchmark
- Python remains only a thin entry/config/output layer
- the main task is to replace Python/Cython orchestration with native exact kernels and eventually a native fullchain loop
