# Accepted After Assemble Branch Layout

- start branch: `feature/cpp-exact-accepted-reaudit-next`
- start commit: `9a7c094`
- new branch: `feature/cpp-exact-accepted-after-assemble-reaudit`
- worktree: `/tmp/feature_cpp_exact_accepted_after_assemble_reaudit`
- scope for this round: exact-only `Assemble_Flux_2` deeper ownership pushdown

## Accepted exact baseline to reproduce

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

## Branch hygiene

- this branch starts clean from the accepted exact checkpoint only
- rejected refresh/fullstep/build-flag/dispatch/external-boundary-deep lines are excluded
- `feature/cpp-exact-accepted-after-extdeep-assemble` is reference-only, not benchmark truth

## Explicitly excluded from commits

- `*.so`
- generated `*.c` / `*.cpp`
- `handoff_network_model_20260312/result/**`
- `reports/*_summary.json`
- `reports/*_perf.json`
- `reports/*_compare.json`
- `reports/*.prof`
- local `bound` symlinks or copied runtime data
