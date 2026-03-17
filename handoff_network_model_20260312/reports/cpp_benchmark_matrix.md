# C++ After Global CFL Benchmark Matrix

## Timing Policy

- headline metric: `evolve/model time`
- initialization excluded
- single-process exact only for accepted status

## Variants

### Accepted historical checkpoint

- source checkpoint: `9a7c094`
- config:
  - accepted exact flags from `feature/cpp-exact-accepted-reaudit-next`
  - `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=0`

### Fresh replay on this branch

- same code and same flags as `9a7c094`
- rebuilt in the clean continuation worktree

### New candidate

- fresh replay plus:
  - `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`

## Results

| Variant | 10m evolve (s) | 2h evolve (s) | 40h evolve (s) | 40h wall (s) | Strict compare |
| --- | ---: | ---: | ---: | ---: | --- |
| Accepted historical `9a7c094` | `0.912919` | `6.680291` | `65.237010` | `69.804079` | yes |
| Fresh replay | `1.039685` | `7.261597` | `69.479726` | `74.814494` | yes |
| Candidate `+ ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1` | `0.709517` | `4.607920` | `60.743103` | `65.648969` | yes |

## Acceptance

The new candidate is accepted for this line because:

- 10m / 2h / 40h strict compare all pass
- 40h exact `evolve/model time` improves clearly:
  - `65.237010 s -> 60.743103 s`
