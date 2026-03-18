# CPP Benchmark Matrix

## Historical Accepted Gate

- source branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- source commit: `445c2c9`

| case | model/evolve time (s) |
| --- | ---: |
| 10m | unknown in this worktree handoff |
| 2h | unknown in this worktree handoff |
| 40h | `47.053824` |

## Fresh Replay On This Branch Baseline

| case | model/evolve time (s) | wall (s) | strict compare |
| --- | ---: | ---: | --- |
| 10m | `0.352145` | `0.378592` | pass |
| 2h | `2.099734` | `2.265646` | pass |
| 40h | `39.178308` | `41.383760` | pass |

## Source Deep V1 Candidate

| case | model/evolve time (s) | wall (s) | strict compare |
| --- | ---: | ---: | --- |
| 10m | `0.306177` | `0.331014` | pass |
| 2h | `2.102745` | `2.271844` | pass |
| 40h | `34.265936` | `38.366420` | pass |

## Gate Outcome

- historical accepted 40h gate: `47.053824 s`
- candidate 40h: `34.265936 s`
- accepted-gate result: **pass**
- same-harness fresh 40h A/B: `39.178308 s -> 34.265936 s`
