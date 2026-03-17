# C++ Accepted Reaudit Benchmark Matrix

## Timing Policy

- headline metric: `evolve/model time`
- initialization excluded
- single-process exact only

## Variants

### Accepted historical checkpoint

- source checkpoint: `9535623`
- config:
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

### Fresh re-audit replay

- same code and same flags as `9535623`
- rebuilt in the clean re-audit worktree

### New candidate

- fresh re-audit replay plus:
  - `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

## Results

| Variant | 10m evolve (s) | 2h evolve (s) | 40h evolve (s) | 40h wall (s) | Strict compare |
| --- | ---: | ---: | ---: | ---: | --- |
| Accepted historical checkpoint `9535623` | 0.667691 | 5.103571 | 91.329929 | 95.239897 | yes |
| Fresh re-audit replay | 1.233370 | 9.695405 | 101.177666 | 105.312057 | yes |
| New candidate with deep rectangular Roe flux | 0.912919 | 6.680291 | 65.237010 | 69.804079 | yes |

## Acceptance

The new candidate is accepted for this line because the gate metric improves clearly:

- `91.329929 s -> 65.237010 s` on 40h exact
