# Global CFL Hotspot Recheck

## Scope

- branch: `feature/cpp-exact-accepted-after-global-cfl`
- start checkpoint: `feature/cpp-exact-accepted-reaudit-next@9a7c094`
- path under audit: accepted exact config only
- timing policy: `evolve/model time` only

## Accepted exact replay on this clean worktree

The accepted exact path was replayed in this clean continuation worktree and compared against the stored `accepted_reaudit_rectdeep_*` outputs.

| Case | Replay evolve (s) | Replay wall (s) | Steps | Strict compare |
| --- | ---: | ---: | ---: | --- |
| 10m | `1.039685` | `1.081289` | `181` | pass |
| 2h | `7.261597` | `7.493120` | `1482` | pass |
| 40h | `69.479726` | `74.814494` | `29783` | pass |

Historical accepted reference from `9a7c094` remains:

- 40h `evolve/model time = 65.23701047897339 s`

## 40h global CFL recheck

Fresh 40h timer buckets on the accepted exact replay:

- `nodechain.total = 44.730091 s`
- `boundary_updater.total = 41.504179 s`
- `river_step.assemble = 7.260691 s`
- `dt_update.global_cfl = 4.258397 s`
- `river_step.update_cell = 3.738485 s`
- `river_step.source = 2.064564 s`

This puts `dt_update.global_cfl` at about `6.13%` of the 40h evolve time on the clean replay.

## Relative priority

Among the non-nodechain follow-on stages, the fresh 40h order is:

1. `river_step.assemble = 7.260691 s`
2. `dt_update.global_cfl = 4.258397 s`
3. `river_step.update_cell = 3.738485 s`
4. `river_step.source = 2.064564 s`

Raw Top 1 is still `boundary_updater / nodechain`, but its remaining obvious deeper pushes are too close to already-rejected refresh/fullstep/residual families. That keeps `global CFL / dt reduction` as the highest-confidence next move that is both:

- still materially large
- and clearly separable from the rejected lines

## Current ownership gap

`dt_update.global_cfl` is still stage-owned by Python / NumPy:

- `cython_cpp_bridge.pyx` calls `net.Caculate_global_CFL()` once per step
- `Rivernet.Caculate_global_CFL()` loops over `self._river_edges` in Python
- each river still calls `River.Caculate_CFL_time_for_river_net()` as a Python method
- per-river candidate calculation still uses NumPy vector ops on:
  - `U`
  - `C`
  - `cell_lengths`
  - `DTI`
- the net-level reduction still builds:
  - `dt_list`
  - `dt_items`
  - Python `min(...)`
  - Python `cfl_history` dict records

## 2h call-path evidence

2h cProfile confirms that the cost is real and still Python-owned:

- `Rivernet.Caculate_global_CFL`: `0.338347 s` cumulative over `1482` calls
- `river_for_net.Caculate_CFL_time_for_river_net`: `0.288204 s` cumulative over `20748` calls

These numbers are smaller than nodechain, but they are cleanly isolated and exact-sensitive, which makes them a better next push than reopening nodechain tail experiments.

## Decision

This recheck confirms the user constraint for this round:

- `global CFL / dt reduction` remains the highest-confidence next move
- it is exact-sensitive but structurally simple
- it is materially different from the rejected refresh/fullstep/build-flag/disptach/external-boundary-deep routes
