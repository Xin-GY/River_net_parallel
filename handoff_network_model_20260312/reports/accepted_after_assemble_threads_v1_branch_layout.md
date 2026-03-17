# Accepted After Assemble Threads V1 Branch Layout

- new branch: `feature/cpp-exact-after-assemble-threads-v1`
- worktree: `/tmp/feature_cpp_exact_after_assemble_threads_v1`
- source accepted candidate:
  - branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
  - commit: `445c2c9`
  - subject: `perf: deepen exact assemble ownership on global-cfl baseline (+22.5% 40h evolve)`

## Reproduction Baseline

This continuation starts from the accepted serial exact path with:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## Scope Guard

This branch is reserved for the first deterministic C++ native-threads trial on the deep assemble kernel only.

Explicitly excluded from this continuation:

- nodechain threads
- global CFL threads
- update-cell threads
- refresh-deep revivals
- residual / Jacobian revivals
- fullstep / dispatch reshaping
- external-boundary-deep paths
- FAST_MODE
- Python-layer multiprocessing or multithreading
- `-march=native`
- `-ffast-math`

## Local Generated Artifacts Excluded From Commit

- Cython-generated `*.c` / `*.cpp`
- compiled `*.so`
- `build/`
- interpolation cache files under `bound/`
- benchmark JSON / compare JSON / profiler outputs kept outside the branch commit set
