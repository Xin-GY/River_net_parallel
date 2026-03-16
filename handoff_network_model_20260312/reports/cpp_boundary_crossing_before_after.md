# C++ Boundary Crossing Before / After

## Compared Variants

### Baseline for this report

- branch state after accepted phase 3
- flags:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

### Candidate for this report

- same exact configuration plus:
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=1`

## Exactness Status

- 10m compare:
  - `allclose = true`
- 2h compare:
  - `allclose = true`
- 40h compare:
  - `allclose = true`

## Speed Before / After

### 10m

- phase-3 accepted wrapper-bypass:
  - `1.457326 s`
- direct-dispatch bridge:
  - `1.452927 s`
- delta:
  - `-0.004399 s`
  - about `0.30%` faster

### 2h

- phase-3 accepted wrapper-bypass:
  - `11.400661 s`
- direct-dispatch bridge:
  - `11.254503 s`
- delta:
  - `-0.146158 s`
  - about `1.28%` faster

### 2h perf counters

- `boundary_updater.total`
  - `3.969430 s -> 3.929515 s`
- `river_step.face_uc`
  - `0.490581 s -> 0.479804 s`
- `river_step.roe_matrix`
  - `0.983287 s -> 0.969913 s`
- `river_step.source`
  - `0.094393 s -> 0.087512 s`
- `river_step.flux`
  - `2.245914 s -> 2.217786 s`
- `river_step.assemble`
  - `1.700979 s -> 1.670884 s`
- `river_step.update_cell`
  - `1.938252 s -> 1.883655 s`
- `dt_update.global_cfl`
  - `0.192927 s -> 0.190612 s`

## Interpretation

The gain in this phase comes from removing one layer of network wrapper fan-out, not from changing any of the river kernels themselves. The exact step ordering is preserved, but the bridge now drives more of the per-step work directly.

## 40h

- phase-3 accepted wrapper-bypass:
  - `202.210932 s`
- direct-dispatch bridge:
  - `203.544599 s`
- delta vs phase-3 accepted path:
  - `+1.333667 s`
  - about `0.66%` slower

## Conclusion

This direct-dispatch bridge experiment is exact, but it is not accepted:

- it improves 10m and 2h
- it remains faster than the older phase-2 baseline
- but it is slower than the accepted phase-3 wrapper-bypass path on the real 40h full case

So this phase-5 experiment should be kept as a documented branch-local experiment, not merged into the current accepted exact candidate.
