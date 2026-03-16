# Overnight Hand-off

## Branch / Worktree

- branch:
  - `feature/cpp-exact-evolve-kernelize-next`
- worktree:
  - `/tmp/feature_cpp_exact_evolve_kernelize_next`

## Accepted Code Checkpoints

- `13b80ca`
  - corrected single-process exact baseline profiling and hotspot reports
- `2931bda`
  - accepted exact nodechain wrapper-bypass
- `535fb8a`
  - documentation of the exact direct-dispatch bridge experiment

## Current Recommended Exact Configuration

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=0`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

## Current Best 40h Result On This Branch

- evolve/model:
  - `202.210932 s`
- evolve wall:
  - `206.131686 s`
- strict compare:
  - pass

## Documented But Rejected Experiment

- direct-dispatch bridge:
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=1`
- exact:
  - yes
- short-case result:
  - faster
- 40h result:
  - `203.544599 s`
- disposition:
  - rejected as default exact path because it is slower than the accepted phase-3 configuration

## Important Reports

- baseline and hotspots:
  - `reports/cpp_exact_serial_baseline.md`
  - `reports/cpp_hotspots_top10.md`
- accepted nodechain improvement:
  - `reports/cpp_nodechain_kernel_plan.md`
  - `reports/cpp_nodechain_impl.md`
  - `reports/cpp_nodechain_before_after.md`
- documented direct-dispatch experiment:
  - `reports/cpp_fullchain_native_loop_plan.md`
  - `reports/cpp_fullchain_native_loop_impl.md`
  - `reports/cpp_boundary_crossing_before_after.md`
- overall recommendation:
  - `reports/cpp_benchmark_matrix.md`
  - `reports/final_cpp_branch_recommendation.md`

## Uncommitted / Generated Artifacts

The worktree still contains untracked generated files that were intentionally not committed:

- compiled extension outputs:
  - `cython_cpp_bridge.cpp`
  - `cython_cpp_bridge.cpython-311-*.so`
  - `cython_node_iteration.c`
  - `cython_node_iteration.cpython-311-*.so`
  - `cython_river_kernels.c`
  - `cython_river_kernels.cpython-311-*.so`
- invalid or intermediate benchmark artifacts from discarded runs
- raw experiment outputs that are useful for local inspection but not part of the accepted git history

## Recommended Next Move

Continue from the accepted phase-3 exact baseline on this branch, not from the rejected direct-dispatch path.

The next best target is:

1. native exact work on `Update_cell_proprity2`
2. then deeper native ownership of nodechain state commit
3. then a true native river-step workspace to cut Python object dependence inside the step loop
