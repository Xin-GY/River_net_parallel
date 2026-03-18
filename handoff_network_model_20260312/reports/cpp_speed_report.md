# CPP Speed Report

## Accepted Gate

Historical accepted exact gate from the source branch:

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- commit: `445c2c9`
- 40h `evolve/model time = 47.05382442474365 s`

New candidate on this branch:

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- candidate mode: `ISLAM_CPP_USE_SOURCE_DEEP=1`
- 40h `evolve/model time = 34.26593613624573 s`

Accepted-gate speedup:

- absolute gain: `12.787888 s`
- speedup: `1.373x`

## Fresh Replay Before/After

Fresh replay on this worktree baseline:

- 10m: `0.352145 s`
- 2h: `2.099734 s`
- 40h: `39.178308 s`

Source deep v1 candidate:

- 10m: `0.306177 s`
- 2h: `2.102745 s`
- 40h: `34.265936 s`

Fresh-replay speedup on 40h:

- absolute gain: `4.912371 s`
- speedup: `1.143x`

## Stage Before/After On Fresh 40h Replay

- `river_dispatch.Caculate_source_term_2.time`: `1.115864 s -> 0.298392 s`
- `river_step.source`: `1.152433 s -> 0.329018 s`
- `river_step.update_cell`: `1.830265 s -> 1.729327 s`
- `river_step.assemble`: `1.697002 s -> 1.597568 s`
- `boundary_updater.total`: `27.429416 s -> 25.179718 s`
- `boundary_updater.external`: `11.841839 s -> 10.926264 s`
- `nodechain.total`: `28.920906 s -> 26.428349 s`
- `nodechain.apply_and_boundary_closure`: `11.871158 s -> 10.812318 s`
- `nodechain.final_apply`: `1.986383 s -> 1.842736 s`

## Interpretation

The direct source-stage win is large and exact. On this machine it also reduces adjacent shell costs enough to produce a real full-case gain rather than a local-only micro-win.

`source` itself is no longer a first-order blocker after this pushdown. The raw remaining heavy costs are back to:

- `nodechain.total`
- `boundary_updater.total`

but those families still require more caution because the obvious deeper routes are close to already-rejected exact continuations.
