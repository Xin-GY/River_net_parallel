# C++ Accepted Reaudit Speed Report

## Scope

- branch: `feature/cpp-exact-accepted-reaudit-next`
- timing policy: `evolve/model time` only
- initialization is excluded
- only single-process exact runs are considered

## Candidate

Accepted exact checkpoint `9535623`, plus:

- `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

## Historical Accepted Baseline vs New Candidate

| Case | Accepted `9535623` evolve (s) | New candidate evolve (s) | Speedup |
| --- | ---: | ---: | ---: |
| 10m | 0.667691 | 0.912919 | 0.73x |
| 2h | 5.103571 | 6.680291 | 0.76x |
| 40h | 91.329929 | 65.237010 | 1.40x |

## Fresh Reaudit Replay vs New Candidate

The clean replay of `9535623` in this worktree was slower than the historical accepted branch record, but the new candidate still improved it strongly:

| Case | Fresh replay evolve (s) | New candidate evolve (s) | Speedup |
| --- | ---: | ---: | ---: |
| 10m | 1.233370 | 0.912919 | 1.35x |
| 2h | 9.695405 | 6.680291 | 1.45x |
| 40h | 101.177666 | 65.237010 | 1.55x |

## 40h Substage Delta

Relative to the fresh replay:

- `river_step.flux`: `42.333267 s -> 4.547068 s`
- `river_step.assemble`: `7.132460 s -> 6.854175 s`
- `river_step.update_cell`: `4.027083 s -> 3.574104 s`
- `nodechain.total`: `38.318935 s -> 41.519373 s`

## Conclusion

This round is accepted on the full-case gate because:

- strict compare passes on 10m / 2h / 40h
- 40h `evolve/model time` drops from `91.329929 s` to `65.237010 s`

The gain is a real ownership push in the rectangular Roe-flux path, not a dispatch-shape effect.
