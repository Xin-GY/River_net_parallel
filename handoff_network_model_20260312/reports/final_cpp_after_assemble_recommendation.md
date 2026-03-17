# Final CPP After Assemble Recommendation

## Verdict

This round does **not** produce a new accepted exact checkpoint.

## Why

- `Assemble_Flux_2` deeper ownership is exact:
  - 10m strict compare: pass
  - 2h strict compare: pass
  - 40h strict compare: pass
- but the 40h acceptance gate fails on performance:
  - accepted baseline `9a7c094`: `65.23701047897339 s`
  - new candidate: `68.21299862861633 s`

## What improved

- `river_step.assemble`: `7.977036 s -> 3.346388 s`
- end-to-end 40h on this clean replay: `74.175709 s -> 68.212999 s`

## Why it still failed

- raw Top 1 cost is still `nodechain / boundary_updater`
- `dt_update.global_cfl` regressed slightly
- `nodechain.total` stayed effectively flat-to-up
- assemble’s local win was not enough to beat the accepted historical branch record

## Current remaining first-order blocker

Raw first-order blocker on the accepted exact path remains:

- `boundary_updater / nodechain`

But the obvious deeper nodechain routes are still too close to already-rejected refresh/fullstep/residual families.

## Next exact-only move

If exact-only optimization resumes from `9a7c094`, the single best next point should be:

- `global CFL / dt reduction ownership`

Reason:

- it is materially smaller than nodechain, but still real (`~4.7-5.0 s`)
- it is more clearly separable from rejected refresh/fullstep families
- it remains Python/NumPy-owned in the accepted path

## Do not reopen

- `_refresh_cell_state` deeper ownership old variants
- residual / Jacobian deep push
- fullstep / dispatch reshaping
- external-boundary-deep exact
- `-march=native`
- FAST / multi-process / multi-thread benchmark lines
