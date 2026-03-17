# Assemble V2 Hotspot Recheck

## Scope

This recheck was run on top of the accepted global-CFL branch baseline:

- branch: `feature/cpp-exact-accepted-after-global-cfl`
- commit: `689ae0b`
- configuration: accepted exact flags from that branch, including `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`

Fresh replay/compare on this continuation worktree:

- 10m: strict compare pass, `model_time_seconds = 0.731429`
- 2h: strict compare pass, `model_time_seconds = 5.815933`
- 40h: strict compare pass, `model_time_seconds = 50.941080`

The fresh replay is materially faster than the historical accepted checkpoint record (`60.743103 s`). For this branch, all implementation decisions below use the fresh replay as the local before-state, while the external acceptance gate still remains “must beat `60.74310255050659 s`”.

## 40h Cost Recheck

Fresh 40h perf on the accepted exact path:

- `nodechain.total = 33.988113 s`
- `boundary_updater.external = 13.749671 s`
- `nodechain.apply_and_boundary_closure = 13.923207 s`
- `nodechain.final_apply = 2.258724 s`
- `river_step.assemble = 5.869043 s`
- `river_step.update_cell = 2.976607 s`
- `river_step.roe_matrix = 1.295697 s`
- `river_step.source = 1.269551 s`
- `river_step.face_uc = 0.718905 s`
- `dt_update.global_cfl = 0.697966 s`

## Relative Priority

Among the non-nodechain stages, the fresh 40h order is now:

1. `river_step.assemble = 5.869043 s`
2. `river_step.update_cell = 2.976607 s`
3. `river_step.roe_matrix = 1.295697 s`
4. `river_step.source = 1.269551 s`
5. `dt_update.global_cfl = 0.697966 s`
6. `river_step.face_uc = 0.718905 s`

This keeps `Assemble_Flux_2` as the highest-confidence next move outside the nodechain/boundary family.

## Remaining Assemble Ownership Gap

Current `Assemble_Flux_2()` on `689ae0b` is still mixed-ownership:

- Python still owns `_apply_explicit_conservative_increment()`
- Python still owns the stage wrapper and feature routing
- the current native kernel only covers the Manning post-step and conservative dry admissibility
- the conservative increment, stage-local scratch orchestration, and write-back sequencing are not yet fully native-owned

2h cProfile on the accepted exact path confirms the Python shell is still visible:

- `Assemble_Flux_2`: `cumtime = 0.442729 s`
- `_apply_explicit_conservative_increment`: `cumtime = 0.248247 s`

This means the current assemble path is not “fully native-owned”; it is still:

- Python stage entry
- Python conservative increment
- native Manning post-step
- Python return / next-stage handoff

## Why This Round Should Still Target Assemble

Raw Top 1 remains `boundary_updater / nodechain`, but the remaining obvious deeper paths there are still too close to the already-rejected:

- refresh-deep family
- residual / Jacobian deep family
- fullstep / dispatch reshaping family

By contrast, `Assemble_Flux_2` is:

- still materially large (`5.869043 s` on fresh 40h replay)
- already proven exact-safe in the preserved prototype branch
- clearly separable from refresh/fullstep/external-boundary experiments
- a stage where ownership can still be pushed deeper without reopening the rejected nodechain tail family

## Why Not Update Cell / Source / Threads First

- `Update_cell_proprity2` is smaller than assemble on the new baseline and its deeper variants are much closer to the rejected refresh-deep family.
- `source` is materially smaller than assemble and has less obvious ownership slack.
- `dt_update.global_cfl` is already down to `0.697966 s`; this branch family already captured the clean win there.
- C++ threads are not the right next move yet, because the serial assemble ownership gap is still larger and better isolated than any deterministic-thread opportunity.

## Verdict

`Assemble_Flux_2` remains the single highest-confidence next move on top of `689ae0b`.

No alternative candidate is retained for this round.
