# Assemble Deep Exact Speed Report

## Scope

- branch: `feature/cpp-exact-accepted-after-assemble-reaudit`
- timing policy: `evolve/model time` only
- initialization excluded
- single-process exact only

## Historical Accepted Baseline vs Candidate

| Case | Accepted `9a7c094` evolve (s) | Candidate evolve (s) | Speedup |
| --- | ---: | ---: | ---: |
| 10m | `0.912919` | `0.965080` | `0.95x` |
| 2h | `6.680291` | `6.509730` | `1.03x` |
| 40h | `65.237010` | `68.212999` | `0.96x` |

## Fresh Replay vs Candidate

| Case | Fresh accepted replay evolve (s) | Candidate evolve (s) | Speedup |
| --- | ---: | ---: | ---: |
| 10m | `0.926752` | `0.965080` | `0.96x` |
| 2h | `7.167058` | `6.509730` | `1.10x` |
| 40h | `74.175709` | `68.212999` | `1.09x` |

## 40h Substage Delta vs Fresh Replay

- `river_step.assemble`: `7.977036 s -> 3.346388 s`
- `river_step.update_cell`: `4.373534 s -> 3.793455 s`
- `river_step.source`: `2.105420 s -> 2.077177 s`
- `dt_update.global_cfl`: `4.706568 s -> 4.983562 s`
- `boundary_updater.total`: `41.971656 s -> 41.342280 s`
- `nodechain.total`: `43.545678 s -> 43.746039 s`

## Conclusion

This path improves the clean replay and does cut the assemble stage substantially, but it does **not** beat the accepted historical exact baseline on the 40h gate.

- accepted gate target: `< 65.23701047897339 s`
- candidate result: `68.21299862861633 s`

So this round is a preserved exact prototype, not a new accepted checkpoint.
