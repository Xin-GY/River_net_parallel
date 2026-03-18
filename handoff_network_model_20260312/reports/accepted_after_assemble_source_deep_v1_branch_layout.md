# Accepted After Assemble Source Deep V1 Branch Layout

## Authoritative starting point

- accepted exact starting branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- accepted exact starting commit: `445c2c9`
- accepted exact 40h gate: `47.05382442474365 s`

`main` branch index documents are stale for this round and remain informational only.

## This continuation

- continuation branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- continuation worktree: `/tmp/feature_cpp_exact_after_assemble_source_deep_v1`
- purpose: audit and, only if justified, deepen exact serial ownership for `Caculate_source_term_2`

## Required accepted exact configuration

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

## Excluded generated artifacts

These must stay out of any source commit on this continuation:

- `*.so`
- generated Cython `*.c` / `*.cpp`
- `reports/*_summary.json`
- `reports/*_perf.json`
- `reports/*_compare.json`
- `reports/*.prof`
- `result/**`
- local links and ad-hoc symlinks

At phase-0 capture time, `git ls-files --others --exclude-standard` was empty in this worktree.
There are tracked C++ sources under `handoff_network_model_20260312/cpp/*.cpp`; those are part of the repository and are not generated artifacts.

## Explicitly out of scope

Do not mix in code from:

- boundary shell v1 continuation
- assemble threads v1 continuation
- external-boundary-deep
- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping
- build-flag experiments
- thread experiments of any kind

This round is source-term only unless the phase-1 audit proves that source-term is not the highest-confidence next move.
