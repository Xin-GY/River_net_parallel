# C++ After Global CFL Speed Report

## Scope

- branch: `feature/cpp-exact-accepted-after-global-cfl`
- timing policy: `evolve/model time` only
- initialization is excluded
- only single-process exact serial runs are accepted in this round

## Candidate

Accepted exact checkpoint `9a7c094`, plus:

- `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`

## Historical Accepted Baseline vs New Candidate

Historical accepted reference from the source branch:

- 40h accepted exact `evolve/model time = 65.23701047897339 s`

New candidate:

- 40h exact `evolve/model time = 60.74310255050659 s`

Speedup:

- `65.237010 / 60.743103 = 1.074x`
- absolute gain: `4.493908 s`

## Fresh Replay vs New Candidate

The clean replay of `9a7c094` in this worktree was slower than the historical accepted record, but the new candidate still improved it strongly:

| Case | Fresh replay evolve (s) | New candidate evolve (s) | Speedup |
| --- | ---: | ---: | ---: |
| 10m | `1.039685` | `0.709517` | `1.47x` |
| 2h | `7.261597` | `4.607920` | `1.58x` |
| 40h | `69.479726` | `60.743103` | `1.14x` |

## 40h Substage Delta

Relative to the fresh replay:

- `dt_update.global_cfl`: `4.258397 s -> 0.728253 s`
- `boundary_updater.total`: `41.504179 s -> 38.832676 s`
- `nodechain.total`: `44.730091 s -> 41.198503 s`
- `river_step.assemble`: `7.260691 s -> 6.546105 s`
- `river_step.update_cell`: `3.738485 s -> 3.354221 s`
- `river_step.source`: `2.064564 s -> 1.958426 s`

## Thread Trial Recheck

This round did **not** continue into C++ native threads.

Reason:

- the serial native path already cut `dt_update.global_cfl` down to `0.728253 s`
- after that reduction, `global CFL / dt reduction` is no longer large enough to justify a thread experiment as the next move in the same round
- keeping the accepted path serial avoids adding a second acceptance dimension after the serial gate already passed cleanly
