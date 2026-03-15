# Evolve Hotspots Top 3 Serial

## Source Of Truth

- Primary source:
  - `cProfile` on the evolve loop only
- Runs used:
  - 10-minute evolve-only profile
  - 2-hour representative long-case evolve-only profile
- Top 3 selection is based primarily on the 2-hour run because its hotspot ranking is more stable than the short case

## Top 10 From The 2-Hour Evolve-Only Profile

Total evolve wall in profile scope: `81.598755771 s`

1. `Rivernet.Update_boundary_conditions` -> `48.245624 s` (`59.13%`)
2. `Rivernet.Update_internal_boundary_conditions` -> `45.519832 s` (`55.78%`)
3. `Rivernet._apply_internal_node_levels` -> `43.308049 s` (`53.07%`)
4. `Rivernet.Apply_node_target_level_V4` -> `43.238363 s` (`52.99%`)
5. `river_for_net.OutBound_Fix_level_V3` -> `27.768763 s` (`34.03%`)
6. `river_for_net._resolve_stage_boundary_chi_bundle` -> `19.181041 s` (`23.51%`)
7. `river_for_net._refresh_cell_state` -> `17.014079 s` (`20.85%`)
8. `river_for_net.InBound_Fix_level_V3` -> `14.723173 s` (`18.04%`)
9. `river_for_net.Caculate_Roe_Flux_2` -> `13.577339 s` (`16.64%`)
10. `river_for_net.Update_cell_proprity2` -> `9.886540 s` (`12.12%`)

## Confirmed Top 3 Targets

### Top 1: internal node iteration chain

- Primary function anchor:
  - `Rivernet.Update_internal_boundary_conditions`
- Covered subchain:
  - `_apply_internal_node_levels`
  - `Apply_node_target_level_V4`
  - `InBound_Fix_level_V3`
  - `OutBound_Fix_level_V3`
  - node residual
  - `Caculate_node_Ac_at_ghost_cell*`
  - stopping checks
- Why it is hot:
  - repeated per-node/per-branch orchestration
  - repeated Python dict access for `node_levels`
  - repeated branch traversal with Python tuples
  - large number of exact boundary-closure calls
- Decision:
  - this is the first Cython target regardless of any later ranking changes

### Top 2: `river_for_net.Caculate_Roe_Flux_2`

- Cumtime:
  - `13.577339 s`
- Why it is hot:
  - large per-face loop volume
  - general-HR path still spends substantial time in Python outer loops
  - repeated table lookup / width / triplet / interface assembly logic
- Decision:
  - this is the second Cython target on this branch

### Top 3: `river_for_net.Update_cell_proprity2`

- Cumtime:
  - `9.886540 s`
- Why it is hot:
  - full-cell sweep every step across all rivers
  - repeated `_refresh_cell_state(i)` dispatch
  - repeated table-based width/level/perimeter/pressure/radius queries
- Decision:
  - this is the third Cython target on this branch

## Functions Considered But Not Selected As Separate Targets

### `Assemble_Flux_2`

- Cumtime:
  - `6.804679 s`
- Reason not selected:
  - important, but still lower than `Update_cell_proprity2`
  - remains a likely next target if Top 3 work lands cleanly

### `_resolve_stage_boundary_chi_bundle`

- Cumtime:
  - `19.181041 s`
- Reason not selected separately:
  - this cost is already part of the Top 1 nodechain
  - it should be reduced as part of the nodechain Cythonization, not treated as an independent fourth target

### `OutBound_Fix_level_V3` / `InBound_Fix_level_V3`

- Reason not selected separately:
  - they are internal components of the Top 1 nodechain target

## 10-Minute Cross-Check

The 10-minute evolve-only profile shows the same ranking pattern:

1. nodechain / boundary updater
2. `Caculate_Roe_Flux_2`
3. `Update_cell_proprity2`

This gives enough confidence to proceed with:

1. nodechain exact Cython
2. Roe flux exact Cython
3. update-cell exact Cython
