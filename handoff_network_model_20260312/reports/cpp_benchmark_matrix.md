# CPP Benchmark Matrix

## Historical Accepted Reference

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- commit: `445c2c9`
- 40h accepted exact reference: `47.05382442474365 s`

## Same-Harness Baseline vs Final Exact Candidate

| case | baseline model/evolve (s) | candidate model/evolve (s) | baseline wall (s) | candidate wall (s) | strict compare |
| --- | ---: | ---: | ---: | ---: | --- |
| 10m | `0.338803` | `0.364070` | `0.362350` | `0.389550` | pass |
| 2h | `2.762335` | `2.574142` | `2.953043` | `2.748077` | pass |
| 40h | `43.934351` | `44.538749` | `45.176320` | `48.331601` | pass |

## Grouped Attempt Reference

| case | grouped candidate model/evolve (s) | strict compare |
| --- | ---: | --- |
| 10m | `0.313758` | pass |
| 2h | `2.549395` | pass |
| 40h | `39.838713` | fail |

## Gate Outcome

- same-harness exact result: **pass**
- same-harness net speed gain at 40h: **fail**
- historical accepted reference check `44.538749 < 47.053824`: **pass**

Final branch verdict:

- preserve implementation and reports
- do not upgrade accepted
