# Source Deep V1 Before / After

## Historical Accepted Gate

- baseline branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- baseline commit: `445c2c9`
- baseline 40h `evolve/model time = 47.05382442474365 s`

## Same-Harness Fresh Replay

Baseline on this worktree with `ISLAM_CPP_USE_SOURCE_DEEP=0`:

- 10m: `0.352145 s`
- 2h: `2.099734 s`
- 40h: `39.178308 s`

Candidate with `ISLAM_CPP_USE_SOURCE_DEEP=1`:

- 10m: `0.306177 s`
- 2h: `2.102745 s`
- 40h: `34.265936 s`

## Source-Stage Impact

- `river_dispatch.Caculate_source_term_2.time`: `1.115864 s -> 0.298392 s`
- `river_step.source`: `1.152433 s -> 0.329018 s`

## Nearby Stage Drift On Fresh 40h Replay

- `river_step.update_cell`: `1.830265 s -> 1.729327 s`
- `river_step.assemble`: `1.697002 s -> 1.597568 s`
- `boundary_updater.total`: `27.429416 s -> 25.179718 s`
- `nodechain.total`: `28.920906 s -> 26.428349 s`

## Interpretation

This round is not just a micro win inside the source stage.

The source-stage deepening is large enough to show up as a real 40h same-harness gain:

- absolute gain: `4.912371 s`
- speedup: `1.143x`

And it beats the historical accepted 40h gate by:

- absolute gain: `12.787888 s`
- speedup: `1.373x`
