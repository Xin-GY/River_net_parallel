# Final C++ Branch Recommendation

## Branch

- branch:
  - `feature/cpp-exact-evolve-kernelize-next`
- worktree:
  - `/tmp/feature_cpp_exact_evolve_kernelize_next`
- anchor start:
  - `835cf1f`

## Checkpoints

- `07ed638`
  - preflight and branch layout
- `33374dc`
  - call-chain and dataflow reports
- `13b80ca`
  - corrected serial baseline and hotspot profiling
- `2931bda`
  - accepted exact nodechain wrapper-bypass
- `535fb8a`
  - documented exact direct-dispatch bridge experiment, rejected for full-case default use

## What Is Complete

### Internal node iteration

- yes, the nodechain has been pushed one layer deeper than the original bridge line
- accepted exact improvement:
  - bypass the Python `InBound_Fix_level_V3` / `OutBound_Fix_level_V3` wrapper shell when the existing exact compiled stage-boundary fast path accepts the state

### Evolve hotspot work

The branch has not yet completed the full “Top 3 all native C++ kernels” target, but it has completed:

- accepted nodechain shell improvement
- baseline / hotspot / crossing reports needed to drive the next kernelization stage
- a documented fullchain orchestration experiment

## Current Best Exact Configuration

Use:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=0`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

This is the current recommended exact configuration for this branch.

## Speed Summary

Relative to the corrected phase-2 baseline on this branch:

- 10m:
  - `1.459050 s -> 1.457326 s`
- 2h:
  - `12.330136 s -> 11.400661 s`
- 40h:
  - `206.306033 s -> 202.210932 s`

Relative to the original `835cf1f` bridge checkpoint:

- 40h:
  - `205.593739 s -> 202.210932 s`
  - about `1.65%` faster

## Exactness

The accepted phase-3 configuration is exact on:

- 10m
- 2h
- 40h

The phase-5 direct-dispatch bridge is also exact after the dt-order fix, but it is rejected because it is slower on the 40h full case.

## Why This Branch Is Worth Keeping

Yes, this branch should be treated as the new single-process exact C++ effort baseline because it is:

1. faster than the original bridge checkpoint
2. faster than the corrected phase-2 baseline on the real 40h case
3. still exact on all validation windows
4. better documented, with clear evidence about which deeper-native directions helped and which did not

## Why It Still Lags The Historical ~150s Routes

The remaining gap is still dominated by:

1. nodechain
   - exact closure math is compiled, but the nodechain is not yet a full native object model
2. river-step kernels
   - `Caculate_Roe_Flux_2`
   - `Update_cell_proprity2`
   - `Assemble_Flux_2`
3. boundary crossings / orchestration
   - even after wrapper bypass, the step loop still depends on Python river objects and Python-owned state
4. memory layout
   - the branch still relies on Python object containers instead of a fully native runtime workspace

## Recommended Next 3 Targets

1. move `Update_cell_proprity2` deeper into native exact code without drift
2. move more of the nodechain state commit / ghost-cell update path out of Python-owned methods
3. build a truly native per-river step workspace so the bridge no longer depends on Python river objects inside the tight loop

## Directions To Avoid Repeating

- direct in-nodechain width-ref substitution for the exact path
  - rejected due drift
- first-cut direct numeric stage-boundary closure from `cython_node_iteration.pyx`
  - rejected due segmentation fault
- bridge direct-dispatch as a default exact path
  - exact, but net negative on 40h
