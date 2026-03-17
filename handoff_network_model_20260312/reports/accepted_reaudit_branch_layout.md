# Accepted Reaudit Branch Layout

- branch: `feature/cpp-exact-accepted-reaudit-next`
- worktree: `/tmp/feature_cpp_exact_accepted_reaudit_next`
- start commit: `9535623`
- baseline code source:
  - accepted exact checkpoint only
  - no rejected refresh/fullstep/build-flag variants carried forward

## accepted exact configuration

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## benchmark execution rule

- always run from worktree root:
  - `/tmp/feature_cpp_exact_accepted_reaudit_next`
- invoke:
  - `handoff_network_model_20260312/tools/profile_cpp_exact_serial.py`
- never run the benchmark from inside `handoff_network_model_20260312/`

## explicitly excluded from commit

From the current continuation family, the following remain generated or rejected-artifact material and must not be mixed into this branch:

- Cython generated `*.c` / `*.cpp`
- built extension `*.so`
- `handoff_network_model_20260312/result/*`
- temporary compare/perf/summary json files
- any local `bound` symlink or copied case-input mirror under `handoff_network_model_20260312/`
- any rejected refresh/fullstep/build-flag experiment code or reports beyond context reading
