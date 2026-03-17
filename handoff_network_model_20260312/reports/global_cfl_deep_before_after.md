# Global CFL Deep Before/After

## 40h stage delta

Relative to the accepted exact replay in this worktree:

- `dt_update.global_cfl`: `4.258397 s -> 0.728253 s`
- `boundary_updater.total`: `41.504179 s -> 38.832676 s`
- `nodechain.total`: `44.730091 s -> 41.198503 s`
- `river_step.assemble`: `7.260691 s -> 6.546105 s`
- `river_step.update_cell`: `3.738485 s -> 3.354221 s`
- `river_step.source`: `2.064564 s -> 1.958426 s`

## End-to-end delta

- fresh replay 40h: `69.479726 s`
- candidate 40h: `60.743103 s`
- accepted historical 40h reference: `65.237010 s`

## Reading

This is not just a tiny local timer win. The deep global-CFL path removes most of the Python/NumPy ownership from a stage that runs `29783` times in 40h, and the result is large enough to beat the accepted historical checkpoint as well.
