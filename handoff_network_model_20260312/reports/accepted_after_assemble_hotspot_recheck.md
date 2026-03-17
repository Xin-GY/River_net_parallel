# Accepted After Assemble Hotspot Recheck

## Scope

- branch: `feature/cpp-exact-accepted-after-assemble-reaudit`
- start checkpoint: `feature/cpp-exact-accepted-reaudit-next@9a7c094`
- audit target: accepted exact config only
- timing policy: `evolve/model time` only
- benchmark entrypoint: `tools/profile_cpp_exact_serial.py` from the worktree root

## Accepted exact replay on this clean worktree

The clean replay is slower than the historical accepted branch record, but it is exact against the stored accepted outputs.

| Case | Replay evolve (s) | Replay wall (s) | Steps | Strict compare vs `accepted_reaudit_rectdeep_*` |
| --- | ---: | ---: | ---: | --- |
| 10m | `0.926752` | `0.987833` | `181` | pass |
| 2h | `7.167058` | `7.423156` | `1482` | pass |
| 40h | `74.175709` | `78.970642` | `29783` | pass |

Historical accepted reference on the source branch remains:

- 40h `evolve/model time = 65.23701047897339 s`

This means the fresh audit should be used for blocker ordering, not for replacing the accepted benchmark reference.

## 40h assemble recheck

Fresh 40h timer buckets on the accepted exact replay:

- `nodechain.total = 43.545678 s`
- `boundary_updater.total = 41.971656 s`
- `river_step.assemble = 7.977036 s`
- `dt_update.global_cfl = 4.706568 s`
- `river_step.update_cell = 4.373534 s`
- `river_step.source = 2.105420 s`

## Assemble priority relative to nearby stages

Current 40h ranking among the non-nodechain follow-on stages:

1. `river_step.assemble = 7.977036 s`
2. `dt_update.global_cfl = 4.706568 s`
3. `river_step.update_cell = 4.373534 s`
4. `river_step.source = 2.105420 s`

So assemble is still clearly ahead of update-cell, source, and global CFL reduction as the next high-confidence ownership target outside the already-accepted nodechain and Roe-flux gains.

## Current ownership boundary

`Assemble_Flux_2` is in a mixed state:

- the stage already has a native post-step kernel behind `ISLAM_CPP_USE_ASSEMBLE=1`
- but the Python stage shell still owns the conservative increment + post-step choreography
- the stage boundary between explicit flux accumulation, exact Manning post-step, conservative dry admissibility, and write-back is not yet fully native-owned
- the preserved prototype branch shows a deeper ownership shape is feasible without reopening rejected refresh/fullstep/external-boundary-deep logic

## Why this round should only do assemble

- nodechain is still larger in raw total time, but the obvious deeper pushes there are too close to already-rejected refresh/fullstep/residual families
- source is materially smaller than assemble on the accepted exact replay
- global CFL reduction is smaller than assemble and still a shell-stage reducer rather than a deep ownership stage
- update-cell already has a native exact kernel and is smaller than assemble in the current accepted path

## Decision

This fresh audit supports the user constraint for this round:

- `Assemble_Flux_2` remains the highest-confidence exact-only next move
- it is a real 40h cost center
- it is not a repeat of the rejected refresh/fullstep/external-boundary-deep routes
