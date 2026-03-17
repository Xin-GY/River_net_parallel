# Overnight Hand-off

## Branch / Worktree

- branch:
  - `feature/cpp-exact-accepted-reaudit-next`
- worktree:
  - `/tmp/feature_cpp_exact_accepted_reaudit_next`
- start checkpoint:
  - `9535623`

## What This Round Did

- reran a clean accepted exact audit from `9535623`
- wrote a fresh blocker map for the still-accepted path
- selected only one next move:
  - deeper exact native ownership for the rectangular Roe-flux path
- implemented and validated that one move

## New Accepted Exact Candidate

Recommended config:

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

## Accepted Outcome

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h `allclose`: `true`
- 40h `evolve/model time`:
  - `91.329929 s -> 65.237010 s`

## Key Reports

- fresh audit:
  - `reports/accepted_exact_fresh_hotspots_top10.md`
  - `reports/accepted_exact_first_order_blockers.md`
  - `reports/accepted_exact_native_gap_map.md`
  - `reports/accepted_exact_single_next_move.md`
- implementation:
  - `reports/cpp_roe_flux_rect_deep_plan.md`
  - `reports/cpp_roe_flux_rect_deep_impl.md`
  - `reports/cpp_roe_flux_rect_deep_before_after.md`
- final:
  - `reports/cpp_error_report.md`
  - `reports/cpp_speed_report.md`
  - `reports/cpp_benchmark_matrix.md`
  - `reports/final_cpp_accepted_reaudit_recommendation.md`

## What Not To Reopen

Still rejected:

- refresh deep
- residual/Jacobian deep
- fullstep loop
- build-flag experiments
- `-march=native`
- dispatch / bridge reshaping

## Most Likely Next Blocker

After this round, the largest remaining first-order blocker is back to:

- `boundary_updater / nodechain`

But the previously rejected refresh-deep shapes should not be retried blindly. The next round should start from a fresh audit on this new `65.237010 s` baseline.

## Excluded From Commit

Do not stage:

- generated `*.so`
- generated `*.c` / `*.cpp`
- `result/*`
- compare/perf/summary json outputs
- any local `bound` symlink or copied case-input mirror
