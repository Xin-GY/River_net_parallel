# C++ Benchmark Matrix

## Exact accepted baseline

Source:

- branch family accepted checkpoint `9535623`

Configuration:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

| Case | Model Time (s) | Strict Compare |
| --- | ---: | --- |
| 10m | 0.667691 | pass |
| 2h | 5.103571 | pass |
| 40h | 91.329929 | pass |

## Rejected stage-3 refresh deep experiments

| Candidate | 10m Model Time (s) | 2h Model Time (s) | Exact Status | Decision |
| --- | ---: | ---: | --- | --- |
| Inline Cython refresh | 0.479452 | n/a | fail | reject |
| Single-cell C++ exact refresh | 1.058903 | 8.042586 | pass on 10m/2h | reject, slower |

## Rejected build-flag experiment

Tested flags:

- `ISLAM_BUILD_USE_MARCH_NATIVE=1`

| Case | Accepted Steps | Candidate Steps | Accepted Model Time (s) | Candidate Model Time (s) | Exact Status | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 10m | 181 | 7494 | 0.667691 | 22.017317 | fail | reject |
| 2h | 1482 | 8823 | 5.103571 | 25.891549 | fail | reject |

No 40h run was performed for the native-flags build because the 10m/2h exact checks already failed decisively.
