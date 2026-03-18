# UpdateCell V2 Hotspot Recheck

## Scope

This recheck treats `feature/cpp-exact-after-assemble-source-deep-v1@c92a3ca` as the authoritative accepted exact baseline.

The stale `main` branch index was not used as the starting point.

## Evidence Used

This phase-1 decision combines:

1. the accepted branch's own 40h stage-level perf record at `c92a3ca`, which remains the authoritative accepted exact stage breakdown for this code path
2. a fresh local 2h accepted-config cProfile/perf replay on this continuation worktree for ownership attribution

## Current Accepted 40h Cost Ranking

Current accepted 40h stage costs from the `c92a3ca` branch-local accepted reports:

- `nodechain.total = 26.428349 s`
- `boundary_updater.total = 25.179718 s`
- `river_step.update_cell = 1.729327 s`
- `river_step.assemble = 1.597568 s`
- `river_step.source = 0.329018 s`

Interpretation:

- raw Top 1 remains `nodechain / boundary_updater`
- among the remaining clean serial stages, `update_cell` is now larger than both `assemble` and `source`
- `source` has already been accepted on this baseline, and `boundary shell` has already produced an exact no-go in same-harness A/B

## Fresh 2h Ownership Recheck

Fresh local 2h replay on the accepted exact path:

- `model_time_seconds = 69.248262 s`
- `step_count = 1482`

Relevant 2h perf counters:

- `boundary_updater.total = 41.114497 s`
- `boundary_updater.external = 2.108365 s`
- `nodechain.total = 38.746605 s`
- `river_dispatch.Update_cell_proprity2.time = 8.398995 s`
- `river_dispatch.Assemble_Flux_2.time = 5.926860 s`
- `river_dispatch.Caculate_source_term_2.time = 0.096814 s`

Relevant 2h cProfile attribution:

- `Rivernet.call_river_function_by_name`: `cumtime = 27.756773 s`
- `Rivernet.Update_cell_property_net`: `cumtime = 8.409646 s`
- `river_for_net.Update_cell_proprity2`: `cumtime = 8.383633 s`
- `river_for_net._refresh_cell_state`: `cumtime = 14.571875 s`
- `river_for_net._resolve_width_for_state`: `cumtime = 2.559007 s`

The important ownership signal from the fresh 2h replay is:

- the accepted update-cell kernel is already in native/Cython
- but per-cell state exposure still routes through Python `_refresh_cell_state`
- the Python shell still owns:
  - wrapper entry / exit
  - post-kernel per-cell refresh
  - level/depth/U/C/Fr write-back
  - width resolution
  - perimeter / pressure / hydraulic-radius state exposure
  - `QIN[i] = 0` orchestration

## Current Ownership Boundary In `Update_cell_proprity2`

Already native-owned on the accepted path:

- accepted `update_cell_properties_exact_cpp` kernel
- core state-derivation math inside that kernel
- dry/wet counter increment handoff from the kernel

Still mixed / Python-owned around the accepted kernel:

- `Update_cell_proprity2()` wrapper dispatch
- Python fallback routing
- surrounding `_refresh_cell_state(i)` per-cell loop when the deep shell is not taken
- Python/Cython state exposure for:
  - `water_level`
  - `water_depth`
  - `U`
  - `C`
  - `FR`
  - `P`
  - `PRESS`
  - `R`
- Python width resolution via `_resolve_width_for_state(...)`
- Python `QIN[i] = 0` loop

## Why This Round Should Target Update Cell

### Why not boundary shell

`boundary_shell_v1` already showed:

- shell-only deepening can remain exact
- same-harness 40h A/B produced no net gain
- grouped evaluator batching fails exactness at 40h

So this family remains paused.

### Why not assemble threads

`assemble_threads_v1` already concluded:

- deterministic threads were structurally possible
- the grain size was too small
- not worth first-thread implementation

That family remains paused.

### Why not source again

`source_deep_v1` is now accepted and has already reduced `source` to a small stage. It is no longer the right next target.

### Why not nodechain deeper families

The remaining obvious nodechain continuations are still too close to already-rejected families:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping

This round should not reopen them.

### Why not update-cell threads

This round is deliberately serial-only:

- the user explicitly ruled out `update_cell threads` for this pass
- the remaining issue is still ownership shape, not thread parallelism
- the stage still exposes enough Python/Cython shell that serial deepening should come before any thread discussion

## Unique Decision

`Update_cell_proprity2` wrapper/state-exposure shell remains the single continuation target for this round.

No parallel candidate is retained.

## Phase-1 Verdict

Proceed to `Update_cell_proprity2` serial exact wrapper/state-exposure shell pushdown.
