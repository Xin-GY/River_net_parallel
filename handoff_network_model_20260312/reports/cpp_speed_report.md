# CPP Speed Report

## Accepted Gate

Historical accepted exact gate from the source branch:

- branch: `feature/cpp-exact-accepted-after-global-cfl`
- commit: `689ae0b`
- 40h `evolve/model time = 60.74310255050659 s`

New candidate on this branch:

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- candidate mode: `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
- 40h `evolve/model time = 47.05382442474365 s`

Accepted-gate speedup:

- absolute gain: `13.689278 s`
- speedup: `1.291x`

## Fresh Replay Before/After

Fresh replay on this worktree before v2:

- 10m: `0.731429 s`
- 2h: `5.815933 s`
- 40h: `50.941080 s`

Assemble deep v2 candidate:

- 10m: `0.768293 s`
- 2h: `5.329252 s`
- 40h: `47.053824 s`

Fresh-replay speedup on 40h:

- absolute gain: `3.887255 s`
- speedup: `1.083x`

## Stage Before/After On Fresh 40h Replay

- `river_step.assemble`: `5.869043 s -> 2.428812 s`
- `river_step.update_cell`: `2.976607 s -> 2.673096 s`
- `river_step.source`: `1.269551 s -> 1.244976 s`
- `river_step.roe_matrix`: `1.295697 s -> 1.277582 s`
- `river_step.face_uc`: `0.718905 s -> 0.710665 s`
- `dt_update.global_cfl`: `0.697966 s -> 0.667256 s`
- `nodechain.total`: `33.988113 s -> 34.057932 s`
- `boundary_updater.total`: `32.159558 s -> 32.375613 s`

## Interpretation

The stage-local assemble win is large enough on top of the new global-CFL baseline to overcome the small nodechain/boundary regressions, so the result is now accepted rather than just preserved as a prototype.
