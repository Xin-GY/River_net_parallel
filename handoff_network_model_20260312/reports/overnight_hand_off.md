# Overnight Hand-off

## Branch / Worktree

- branch:
  - `feature/cpp-exact-accepted-after-assemble-reaudit`
- worktree:
  - `/tmp/feature_cpp_exact_accepted_after_assemble_reaudit`
- start checkpoint:
  - `feature/cpp-exact-accepted-reaudit-next@9a7c094`

## What this round did

- created a clean continuation from the current accepted exact baseline
- reran the accepted exact configuration on:
  - 10m
  - 2h
  - 40h
- confirmed exact replay against the stored accepted rectdeep outputs
- rechecked assemble-only ownership priority
- implemented one isolated feature flag:
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
- validated that candidate on:
  - 10m
  - 2h
  - 40h

## Current result

- exactness:
  - 10m pass
  - 2h pass
  - 40h pass
- 40h `allclose`: `true`
- 40h `evolve/model time`:
  - accepted baseline `9a7c094`: `65.23701047897339 s`
  - candidate with `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`: `68.21299862861633 s`

## Recommendation

- do **not** upgrade this path as the new accepted exact baseline
- keep the deeper assemble path as a preserved exact prototype behind its feature flag

## Why it failed the acceptance gate

- assemble itself improved strongly:
  - `7.977036 s -> 3.346388 s`
- but the raw first-order cost still sits in:
  - `boundary_updater / nodechain`
- and `dt_update.global_cfl` got slightly worse, leaving the end-to-end 40h result slower than `9a7c094`

## Key reports

- preflight / audit:
  - `reports/accepted_after_assemble_preflight_git_status.txt`
  - `reports/accepted_after_assemble_branch_layout.md`
  - `reports/accepted_after_assemble_hotspot_recheck.md`
- implementation:
  - `reports/assemble_deep_plan.md`
  - `reports/assemble_deep_impl.md`
  - `reports/assemble_deep_before_after.md`
- compare:
  - `reports/assemble_deep_10m_compare.md`
  - `reports/assemble_deep_2h_compare.md`
  - `reports/assemble_deep_40h_compare.md`
- final:
  - `reports/cpp_error_report.md`
  - `reports/cpp_speed_report.md`
  - `reports/cpp_benchmark_matrix.md`
  - `reports/final_cpp_after_assemble_recommendation.md`

## Next exact-only move

If the exact line continues from the still-accepted baseline `9a7c094`, the best next single point is:

- `global CFL / dt reduction ownership`

## Do not reopen

- refresh-deep old variants
- residual / Jacobian deep push
- fullstep / dispatch reshaping
- external-boundary-deep exact
- `-march=native`
- FAST / multi-process / multi-thread benchmark routes
