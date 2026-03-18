# Boundary Shell V1 Hotspot Recheck

## Baseline

- accepted source branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- accepted source commit: `445c2c9`
- accepted exact gate reference: `40h evolve/model time = 47.05382442474365 s`
- this audit intentionally ignores the stale `main` branch index and uses `445c2c9` as the authoritative baseline

## Fresh Audit Method

- worktree: `/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1`
- accepted exact flags matched the `445c2c9` accepted path
- local audit reran:
  - 2h cProfile attribution
  - 40h perf replay
- to avoid the missing local `h5netcdf` dependency from dominating the audit, the replay kept accepted exact numerics and history export intact but skipped final netcdf dataset writes only

## Fresh 40h Cost Recheck

Fresh 40h replay on the accepted exact path:

- `boundary_updater.total = 28.601873 s`
- `boundary_updater.external = 12.427106 s`
- `nodechain.total = 30.015759 s`
- `nodechain.apply_and_boundary_closure = 12.286190 s`
- `nodechain.final_apply = 2.083110 s`
- `river_step.update_cell = 1.997352 s`
- `river_step.assemble = 1.845583 s`
- `river_step.source = 1.150012 s`
- `dt_update.global_cfl = 0.567658 s`

Relative ranking outside the already-rejected nodechain-deeper families is therefore:

1. `boundary_updater.external = 12.427106 s`
2. `river_step.update_cell = 1.997352 s`
3. `river_step.assemble = 1.845583 s`
4. `river_step.source = 1.150012 s`
5. `dt_update.global_cfl = 0.567658 s`

## Ownership Boundary Today

### `Rivernet.Update_boundary_conditions()`

- top-level step shell is still Python
- external path calls `Update_external_boundary_conditions_V2()`
- internal path calls `Update_internal_boundary_conditions()`

### `Rivernet.Update_external_boundary_conditions_V2()`

Current accepted external path is still Python-owned in the hot loop:

- Python `for` loop over `external_in_nodes`
- Python `for` loop over `_out_branches_by_node[node]`
- Python `for` loop over `external_out_nodes`
- Python `for` loop over `_in_branches_by_node[node]`
- Python `btype` dispatch
- repeated `get_boundary_value(node, t)`
- repeated per-node call to shared inflow hydrograph closure
- repeated per-node call setup / bound-method dispatch

What it does **not** do in this round:

- it does not numerically deepen the accepted boundary formulas themselves
- it does not reopen the rejected external-boundary-deep path

### `Rivernet.Update_internal_boundary_conditions()`

- remains mixed Python / Cython / native-owned
- still large in raw cost
- but the obvious deeper ownership routes there remain too close to the already-rejected refresh / residual / fullstep families
- this round therefore does not reopen it

## External Boundary Topology Facts

Current accepted topology remains:

- 7 inflow nodes
- 1 outflow node
- 8 external branch ops per global step in fixed order
- inflows share one hydrograph source
- outflow uses one level source

That means the main reducible external cost is not “many branches”; it is:

- repeated Python shell traversal
- repeated shared-evaluator work
- repeated per-op routing / call coordination

## 2h cProfile Attribution

2h cProfile on the accepted path:

- `Update_external_boundary_conditions_V2`: `cumtime = 1.344 s`
- `get_boundary_value`: `cumtime = 0.412 s`
- `q_boundary_value`: `cumtime = 0.357 s`
- `level_boundary_value`: `cumtime = 0.042 s`
- `persistent_interpolator.__call__`: `cumtime = 0.385 s`
- `InBound_In_Q2`: `cumtime = 0.859 s`
- `OutBound_Fix_level_V3`: `cumtime = 0.042 s`

Conservative interpretation:

- formula body visible in the accepted external path is about `0.901 s / 2h`
- external shell entry is `1.344 s / 2h`
- residual shell / evaluator / dispatch overhead is therefore still about `0.443 s / 2h`

Scaled by the actual accepted 40h step count, that implies about `8.9 s` of reducible shell / evaluator cost over 40h, well above this round’s go gate.

## Go / No-Go Decision

### Gate

Proceed only if reducible external shell / evaluator overhead is at least:

- `2.0 s` on 40h
- or `15%` of `boundary_updater.external`

### Result

Go.

Reason:

- fresh 40h `boundary_updater.external = 12.427106 s`
- `15%` of that is `1.864066 s`
- conservative shell / evaluator residual estimate is about `8.9 s / 40h`

## Why This Round Should Only Do Boundary Shell

Do not switch to:

- `assemble threads`
  - already audited as too fine-grained
- `nodechain deeper refresh/final tail`
  - too close to already-rejected refresh / residual / fullstep families
- `source`
  - materially smaller than `boundary_updater.external`
- `update_cell`
  - smaller than `boundary_updater.external` and more entangled with state exposure

## Verdict

`boundary_updater` external routing / dispatch shell is the single highest-confidence next move on top of `445c2c9`.

No alternative blocker is retained for this round.
