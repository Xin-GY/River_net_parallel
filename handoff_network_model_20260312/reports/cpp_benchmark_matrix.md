# C++ Kernelize-Next Benchmark Matrix

## Timing Policy

- only `evolve/model time` is treated as the headline metric
- initialization, Fine interpolation, section-table build, coordinate conversion, and final write-out are excluded from the headline metric

## Configurations

### Phase-2 baseline

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=0`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=0`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

### Phase-3 accepted exact candidate

- phase-2 baseline plus:
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`

### Phase-5 documented but rejected experiment

- phase-3 accepted candidate plus:
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=1`

## Results

| Variant | 10m evolve (s) | 2h evolve (s) | 40h evolve (s) | 40h wall (s) | Exact compare |
| --- | ---: | ---: | ---: | ---: | --- |
| Phase-2 baseline | 1.459050 | 12.330136 | 206.306033 | 210.424964 | yes |
| Phase-3 accepted exact | 1.457326 | 11.400661 | 202.210932 | 206.131686 | yes |
| Phase-5 direct-dispatch | 1.452927 | 11.254503 | 203.544599 | 207.500405 | yes |

## Relative Deltas

### Phase-3 accepted exact vs phase-2 baseline

- 10m:
  - `-0.001724 s`
  - `-0.12%`
- 2h:
  - `-0.929476 s`
  - `-7.54%`
- 40h:
  - `-4.095101 s`
  - `-1.98%`

### Phase-5 direct-dispatch vs phase-3 accepted exact

- 10m:
  - `-0.004399 s`
  - `-0.30%`
- 2h:
  - `-0.146158 s`
  - `-1.28%`
- 40h:
  - `+1.333667 s`
  - `+0.66%`

## Current Best Exact Choice

The current best exact configuration on this branch is still the phase-3 wrapper-bypass candidate:

- exact on 10m / 2h / 40h
- faster than the phase-2 baseline on the full case
- faster than the original `835cf1f` bridge checkpoint

The phase-5 direct-dispatch bridge is exact, but it is not the current best full-case performer.
