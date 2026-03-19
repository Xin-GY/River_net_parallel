# After Source Next Audit Hotspot Recheck

## Scope

This audit treats `feature/cpp-exact-after-assemble-source-deep-v1@c92a3ca` as the only authoritative accepted exact baseline.

The stale `main` branch index was not used as a starting point.

## Runtime Validity Note

The first fresh replay on this audit worktree was not trustworthy because the worktree initially lacked the in-place compiled extension modules.

Before drawing any conclusions, the local Cython/C++ extensions were rebuilt in `/tmp/feature_cpp_exact_after_source_next_audit/handoff_network_model_20260312`, and the accepted runtime readiness was rechecked:

- general-HR Roe flux ready
- rectangular Roe flux ready
- source deep ready
- update-cell native plan ready

Only the rebuilt-runtime 2h/40h results below are used for this audit conclusion.

## Authoritative Accepted Ranking

The accepted `c92a3ca` branch reports remain the truth for the current accepted result:

- `nodechain.total = 26.428349 s`
- `boundary_updater.total = 25.179718 s`
- `river_step.update_cell = 1.729327 s`
- `river_step.assemble = 1.597568 s`
- `river_step.source = 0.329018 s`

Accepted 40h evolve/model time remains:

- `34.26593613624573 s`

## Fresh Rebuilt 40h Replay For Stage Ranking

Fresh 40h replay on this audit worktree after rebuilding extensions:

- `model_time_seconds = 38.009132 s`
- `step_count = 29783`

This local replay is slower than the accepted branch result and must not replace the accepted truth. It is used only to re-rank the current stages on a valid runtime.

Key rebuilt-runtime 40h stage costs:

- `nodechain.total = 28.620029 s`
- `boundary_updater.total = 27.357531 s`
- `boundary_updater.external = 11.893754 s`
- `nodechain.apply_and_boundary_closure = 11.717452 s`
- `nodechain.final_apply = 1.969999 s`
- `river_step.flux = 2.460760 s`
- `river_dispatch.Caculate_Roe_Flux_2.time = 2.412462 s`
- `river_step.update_cell = 2.076577 s`
- `river_dispatch.Update_cell_proprity2.time = 2.020924 s`
- `river_step.assemble = 1.837699 s`
- `river_dispatch.Assemble_Flux_2.time = 1.788583 s`
- `river_step.source = 0.354537 s`
- `river_dispatch.Caculate_source_term_2.time = 0.322107 s`
- `river_step.roe_matrix = 0.991126 s`
- `river_step.face_uc = 0.499876 s`
- `dt_update.global_cfl = 0.538512 s`

### Ranking Summary

The ranking that matters did not change:

1. raw Top 1 is still `nodechain / boundary_updater`
2. `flux`, `update_cell`, and `assemble` remain mid-sized clean serial stages
3. `source`, `face_uc`, `roe_matrix`, and global CFL are now smaller supporting stages

## Fresh Rebuilt 2h Ownership Attribution

Fresh official 2h accepted-config replay after rebuilding extensions:

- `model_time_seconds = 4.198845 s`
- `step_count = 1482`

Key perf counters:

- `nodechain.total = 4.187099 s`
- `boundary_updater.total = 3.461901 s`
- `boundary_updater.external = 1.262794 s`
- `nodechain.apply_and_boundary_closure = 1.845580 s`
- `nodechain.final_apply = 0.172403 s`
- `river_step.flux = 0.169727 s`
- `river_step.update_cell = 0.121702 s`
- `river_step.assemble = 0.111703 s`
- `river_step.source = 0.031294 s`
- `dt_update.global_cfl = 0.028847 s`

Key cProfile attribution:

- `call_river_function_by_name`: `ct = 0.532409 s`
- `Update_external_boundary_conditions_V2`: `ct = 1.353832 s`
- `Update_internal_boundary_conditions`: `ct = 2.105920 s`
- `_caculate_roe_flux_general_hr`: `ct = 0.132382 s`
- `Caculate_Roe_Flux_2`: `ct = 0.154350 s`
- `Update_cell_proprity2`: `ct = 0.107474 s`
- `_refresh_cell_state`: `ct = 1.866053 s`

## Remaining Ownership Gap Recheck

### `nodechain / boundary_updater`

Still the dominant raw cost family.

Remaining visible tail:

- Python boundary updater entry
- Python external/internal boundary orchestration
- nodechain tail calls into `_refresh_cell_state(...)`
- boundary-face state exposure back to Python attrs
- Python level-cache coordination

But these tails are still tightly entangled with already-rejected families:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping
- boundary grouped batching

### `Update_cell_proprity2`

Fresh audit confirms the earlier `updatecell_v2` no-go:

- accepted native kernel already owns the meaningful update-cell work
- remaining wrapper/state-exposure shell is too thin
- this is not a clean new ownership gap anymore

### `Assemble_Flux_2`

Already accepted as a deep serial path.

Current remaining cost is the residual cost of the accepted implementation, not a newly exposed shell gap. The first deterministic threads audit also already concluded the grain size is too small to justify implementation.

### `Caculate_source_term_2`

Already accepted deep on `c92a3ca`.

Current cost is small and no longer first-order.

### `Caculate_Roe_Flux_2`

This is the only non-nodechain stage that still looks numerically mid-sized at first glance, so it needed an explicit recheck.

Fresh code-path inspection shows:

- rectangular-HR flux already has accepted deep ownership
- the general-HR hot path now enters `cpp_fill_general_hr_flux_exact_deep(self)` with a precompiled table-view plan
- the worktree readiness check confirms that this deep path is active on the accepted runtime

What remains outside the C++ kernel is mostly:

- stage entry
- buffer reset / zeroing
- rain-source post-write bookkeeping

That is not the same thing as a large remaining per-interface ownership gap. The old “general-HR flux still mostly Python-owned” story was true before the deeper accepted flux work, but it is no longer the current accepted state.

The rebuilt-runtime cProfile also does not show evidence of the hot path falling back to a Python per-interface flux loop.

## Stage Classification Result

- `nodechain / boundary_updater`: still large, but too close to rejected families
- `flux`: still material, but no longer shows a large clean ownership gap
- `update_cell`: no-go already confirmed
- `assemble`: already accepted deep, threads no-go
- `source`, `roe_matrix`, `face_uc`, `global_cfl`: now too small

## Phase-1 Verdict

There is no single materially new exact-serial candidate after `c92a3ca`.

This audit should stop at design conclusion rather than starting another implementation branch.
