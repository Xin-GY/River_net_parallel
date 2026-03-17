# Branch Matrix For GitHub

This document is the GitHub entry index for the river-network optimization branches.

## Current headline conclusions

- Best accepted exact checkpoint in the single-process exact C++ family:
  - branch: `feature/cpp-exact-accepted-reaudit-next`
  - commit: `9a7c094`
  - result: 40h exact `evolve/model time = 65.23701047897339 s`
  - 10m / 2h / 40h strict compare: passed
- Best accepted historical process-based exact baseline remains on `main` lineage and is useful as context, but the C++ single-process branch family is now substantially faster in exact evolve-only terms.
- External-boundary-deep is currently a documented exact no-go:
  - short cases pass
  - 40h strict compare fails
  - root cause is downstream of inflow deep ownership, not interpolation math itself

## Recommended branches

| Branch | Head | Status | Best known result | What it is for |
| --- | --- | --- | --- | --- |
| `main` | `dea3202` | `accepted` | exact multi-process baseline lineage | project baseline and runtime-sections/general-HR accepted optimization |
| `feature/cython-exact-nodechain-top3` | `b7243b7` | `accepted` | 40h single-process exact `213.933772 s` | first clean serial Cython exact line |
| `feature/cpp-exact-evolve-fullchain` | `835cf1f` | `accepted` | 40h single-process exact `205.593739 s` | first usable Cython + C++ evolve bridge |
| `feature/cpp-exact-evolve-fullchain-pushdown-next` | `79c6117` | `accepted` | 40h single-process exact `202.210932 s` | nodechain prebound fast-closure accepted checkpoint |
| `feature/cpp-exact-evolve-nodechain-deepnative` | `f8f0db0` | `accepted` | 40h single-process exact `92.091939 s` | deep nodechain apply ownership accepted checkpoint |
| `feature/cpp-exact-evolve-nodecommit-refresh` | `9535623` | `accepted` | 40h single-process exact `91.32992911338806 s` | deep nodechain commit ownership accepted checkpoint |
| `feature/cpp-exact-accepted-reaudit-next` | `9a7c094` | `accepted` | 40h single-process exact `65.23701047897339 s` | current best accepted exact checkpoint |
| `fast-mode-30s` | `77c714e` | `accepted-fast` | fastest 40h wall around `59.38 s`, balanced around `87.27 s` | approximate FAST_MODE line with error reporting |

## Important WIP / no-go branches worth pushing for analysis

| Branch | Head | Status | Why keep it |
| --- | --- | --- | --- |
| `feature/cpp-exact-accepted-reaudit-after-rectflux` | `cb2a1ab` | `no-go` | preserves external-boundary-deep exact failure evidence and analysis |
| `feature/cpp-exact-accepted-after-extdeep-assemble` | `5a276c2` | `wip` | preserves `Assemble_Flux_2` deeper-ownership prototype for later exact audit |
| `feature/cpp-exact-evolve-nodecommit-refresh-wip` | `11da75c` | `wip` | preserves dirty continuation state without polluting accepted `9535623` |
| `feature/cpp-exact-evolve-fullchain-pushdown-wip` | `3630c9c` | `wip` | preserves dirty continuation state without polluting accepted `1d71dee` |
| `feature/cpp-exact-evolve-nodecommit-refresh-next` | `05b01bc` | `no-go` | documents refresh/fullstep/build-flag rechecks and why they are rejected |
| `feature/cpp-exact-evolve-flux-residual-fullstep` | `d26ea2a` | `accepted-history` | accepted Roe-flux deep checkpoint before later nodechain gains |
| `feature/cpp-exact-evolve-fullchain-pushdown` | `1d71dee` | `accepted-history` | accepted update-cell checkpoint before later continuation splits |

## Archived / preservation-only branches

| Branch | Head | Status | Notes |
| --- | --- | --- | --- |
| `backup/pre-cython-branch-20260315-224054` | `367230f` | `archival` | pre-Cython branch preservation |
| `fast_mode_snapshot_20260314` | `4cf4721` | `archival` | preserved FAST snapshot |
| `safety_fast_20260315_194332` | `1901e06` | `archival` | safety preservation only |
| `safety_main_20260314_223414` | `dea3202` | `archival` | safety preservation only |

## Suggested reading order

1. `feature/cpp-exact-accepted-reaudit-next`
   - `reports/final_cpp_accepted_reaudit_recommendation.md`
   - `reports/cpp_benchmark_matrix.md`
   - `reports/overnight_hand_off.md`
2. `feature/cpp-exact-accepted-reaudit-after-rectflux`
   - `reports/accepted_external_boundary_deep_recheck.md`
3. `feature/cpp-exact-accepted-after-extdeep-assemble`
   - `reports/accepted_after_extdeep_assemble_prototype.md`
4. `fast-mode-30s`
   - `reports/final_fastmode_recommendation.md`
   - `reports/fast_sweep_top_candidates.md`

## Do not restart these directions blindly

- `_refresh_cell_state` deeper ownership old variants
- residual / Jacobian deep push
- fullstep / dispatch shape experiments
- `-march=native`
- FAST_MODE approximations when the task is exact-only
- external-boundary-deep exact ownership in its current form
