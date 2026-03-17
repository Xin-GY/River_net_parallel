# Assemble Deep Before/After

## 40h stage delta

Relative to the fresh accepted replay in this worktree:

- `river_step.assemble`: `7.977036 s -> 3.346388 s`
- `river_step.update_cell`: `4.373534 s -> 3.793455 s`
- `river_step.source`: `2.105420 s -> 2.077177 s`
- `dt_update.global_cfl`: `4.706568 s -> 4.983562 s`
- `boundary_updater.total`: `41.971656 s -> 41.342280 s`
- `nodechain.total`: `43.545678 s -> 43.746039 s`

## End-to-end delta

- fresh replay 40h: `74.175709 s`
- candidate 40h: `68.212999 s`
- accepted historical 40h reference: `65.237010 s`

## Reading

The deeper assemble ownership cuts the assemble stage substantially and improves the clean replay, but the savings are not large enough to offset the still-dominant nodechain/boundary shells plus a slight regression in `dt_update.global_cfl`. That leaves the candidate below the accepted historical gate.
