# CPP Benchmark Matrix

## Historical Accepted Gate

- source branch: `feature/cpp-exact-accepted-after-global-cfl`
- source commit: `689ae0b`

| case | model/evolve time (s) |
| --- | ---: |
| 10m | `0.709517` |
| 2h | `4.607920` |
| 40h | `60.743103` |

## Fresh Replay On This Branch Before V2

| case | model/evolve time (s) | wall (s) | strict compare |
| --- | ---: | ---: | --- |
| 10m | `0.731429` | `0.764190` | pass |
| 2h | `5.815933` | `6.124383` | pass |
| 40h | `50.941080` | `55.618210` | pass |

## Assemble Deep V2 Candidate

| case | model/evolve time (s) | wall (s) | strict compare |
| --- | ---: | ---: | --- |
| 10m | `0.768293` | `0.801901` | pass |
| 2h | `5.329252` | `5.646228` | pass |
| 40h | `47.053824` | `51.715103` | pass |

## Gate Outcome

- historical accepted 40h gate: `60.743103 s`
- candidate 40h: `47.053824 s`
- accepted-gate result: **pass**
