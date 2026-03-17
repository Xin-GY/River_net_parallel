# Global CFL Deep Implementation

## What changed

- `cpp/evolve_core.hpp/.cpp`
  - added `compute_river_cfl_candidate_exact(...)`
  - this computes the per-river CFL candidate and fills `DTI` in native float32 order
- `cython_cpp_bridge.pyx`
  - added `calculate_global_cfl_exact_cpp(net)`
  - prebinds river refs and river names once
  - runs the fixed-order serial reduction over river candidates
  - records `cfl_history` without rebuilding `dt_list` / `dt_items`
- `Rivernet.py`
  - added `ISLAM_CPP_USE_GLOBAL_CFL_DEEP`
  - routed `Caculate_global_CFL()` through the deep native path when enabled
- `Islam.py`
  - wired the new env flag into `configure_net_options(...)`
- `tools/profile_cpp_exact_serial.py`
  - added `--use-cpp-global-cfl-deep`

## What stayed out

- no change to time-step scheduling after `cfl_allowed_dt` is produced
- no change to `Set_global_time_step(...)`
- no change to nodechain, source, assemble, update-cell, or save-output paths
- no thread parallelism yet
