# Branch Layout

- Base accepted checkpoint: `9a7c09453d4f09bf93bba9a6a408bb3ae624fcc4`
- New branch: `feature/cpp-exact-accepted-reaudit-after-rectflux`
- New worktree: `/tmp/feature_cpp_exact_accepted_reaudit_after_rectflux`
- Source accepted branch/worktree kept for reference only:
  - branch: `feature/cpp-exact-accepted-reaudit-next`
  - worktree: `/tmp/feature_cpp_exact_accepted_reaudit_next`

## Accepted Exact Reproduction

This branch reuses the currently accepted exact path and must be benchmarked
from the worktree root:

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
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## Explicit Exclusions

This continuation branch does not carry forward any rejected or non-accepted
variants:

- `_refresh_cell_state` deeper ownership experiments
- residual/Jacobian deeper push experiments
- fullstep loop experiments
- bridge/dispatch reshaping experiments
- `-march=native` or any new build-flag experiments
- FAST_MODE and all approximation paths
- multiprocessing/thread benchmarking

The following generated files are excluded from commit scope:

- `*.so`
- Cython generated `*.c` and `*.cpp`
- benchmark JSON / compare JSON / perf JSON / `*.prof`
- `result/*`
- any local `bound` links or copied case inputs
