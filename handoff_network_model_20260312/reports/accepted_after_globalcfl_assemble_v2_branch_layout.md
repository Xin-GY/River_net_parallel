# Assemble V2 Branch Layout

- source accepted branch: `feature/cpp-exact-accepted-after-global-cfl`
- source accepted commit: `689ae0b`
- new continuation branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- worktree path: `/tmp/feature_cpp_exact_after_globalcfl_assemble_reaudit_v2`

## Accepted Exact Baseline

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
- `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## Scope Of This Branch

- fresh re-audit of `Assemble_Flux_2` on top of accepted commit `689ae0b`
- serial exact only for the implementation phase
- deterministic C++ threads only as a later recheck, and only if serial assemble v2 becomes accepted

## Explicitly Excluded

- refresh-deep variants
- residual / Jacobian deep variants
- fullstep / dispatch experiments
- external-boundary-deep variants
- Python-level process / thread benchmark routes
- FAST mode routes
- build-flag experiments such as `-march=native`

## Untracked Artifact Policy

Do not commit any of the following local artifacts:

- `handoff_network_model_20260312/*.so`
- generated Cython sources such as `handoff_network_model_20260312/*.c` and `handoff_network_model_20260312/*.cpp`
- `handoff_network_model_20260312/result/**`
- `handoff_network_model_20260312/reports/*_summary.json`
- `handoff_network_model_20260312/reports/*_perf.json`
- `handoff_network_model_20260312/reports/*_compare.json`
- `handoff_network_model_20260312/reports/*.prof`
- any local symlink or copied helper input outside tracked source
