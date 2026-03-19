# River Threads V2 Clean Branch Layout

## Accepted Baseline

- accepted branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- accepted commit: `c92a3ca`
- accepted 40h exact evolve/model time: `34.26593613624573 s`

## New Continuation Branch

- working branch: `feature/cpp-exact-after-source-riverthreads-v2-clean`
- worktree: `/tmp/feature_cpp_exact_after_source_riverthreads_v2_clean`
- branch purpose: build a deterministic fixed-worker + stage-barrier C++ thread runtime for river-local stages only

## Reference-Only Prototype

- old prototype branch: `feature/cpp-exact-after-source-riverthreads-v1`
- old prototype commit: `2de7d41`
- role in this round: reference only
- explicit non-goal: do not reuse the Python `ThreadPoolExecutor` orchestration from v1

## File Scope For This Round

Thread runtime and stage dispatch:

- `cpp/evolve_core.hpp`
- `cpp/evolve_core.cpp`
- `cython_cpp_bridge.pyx`

Compiled river-local stage execution:

- `cython_river_kernels.pyx`
- `cpp/river_kernels.hpp`
- `cpp/river_kernels.cpp`

Build wiring:

- `build_cython_exact_kernels.py`

## Deliberately Unchanged Families

- `boundary_updater` stays on the main thread
- nodechain / junction solve stays on the main thread
- output writing stays serial
- no refresh/fullstep/residual family work
- no boundary shell or grouped evaluator batching
- no formula changes, no float64 changes, no unordered reductions
