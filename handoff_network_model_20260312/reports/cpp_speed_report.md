# CPP Speed Report

## Historical Accepted Reference

User-provided accepted exact baseline for this round:

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- commit: `445c2c9`
- 40h `evolve/model time = 47.05382442474365 s`

## Same-Harness Fresh Replay

Fresh replay in this branch with the same no-netcdf harness:

- baseline `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP=0`
  - 10m: `0.338803 s`
  - 2h: `2.762335 s`
  - 40h: `43.934351 s`
- final exact candidate `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP=1`
  - 10m: `0.364070 s`
  - 2h: `2.574142 s`
  - 40h: `44.538749 s`

## 40h Stage Breakdown On Same Harness

- `boundary_updater.external`: `12.996334 s -> 14.989032 s`
- `boundary_updater.total`: `29.933907 s -> 32.342391 s`
- `nodechain.total`: `31.562714 s -> 34.368405 s`
- `nodechain.apply_and_boundary_closure`: `12.933993 s -> 14.126568 s`
- `nodechain.final_apply`: `2.222270 s -> 2.396962 s`
- `river_step.assemble`: `1.707317 s -> 1.855085 s`
- `river_step.update_cell`: `1.841285 s -> 2.034387 s`
- `river_step.source`: `1.663362 s -> 1.773751 s`
- `dt_update.global_cfl`: `0.506438 s -> 0.530715 s`

## Grouped Attempt

The first grouped evaluator attempt was faster:

- 40h: `39.838713 s`

but failed exact compare, so it is rejected.

## Interpretation

Final exact boundary-shell v1 is:

- exact
- below the historical accepted `47.053824 s` reference

but also:

- slower than the same-harness fresh replay baseline

So this branch should not be promoted as a new accepted exact result.
