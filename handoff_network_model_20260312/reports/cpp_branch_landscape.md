# Current Branch Landscape

## Accepted / Anchor Lines

- `main @ dea3202`
  - clean repository anchor
  - accepted exact baseline for this project family

- `feature/cython-exact-nodechain-top3 @ b7243b7`
  - single-process cython exact line
  - established:
    - evolve-only timing method
    - exact nodechain kernel
    - exact Roe/general-HR kernel
  - known issue:
    - not yet native fullchain

- `feature/cpp-exact-evolve-fullchain @ 835cf1f`
  - first usable `Cython + C++` exact evolve bridge
  - prepared evolve path can hit `ISLAM_USE_CPP_EVOLVE=1`
  - exact compare passed on 10m / 2h / 40h against same-branch cython exact serial
  - current limitation:
    - bridge gain is only about `0.84 s` on 40h evolve time
    - true numeric work is still not deeply native

## Preserved Experimental Lines

- `fast-mode-30s`
- `fast_mode_snapshot_20260314`
- `exact-baseline-clean`
- safety / backup branches

These remain preserved for audit and historical comparison, but are not part of the current single-process exact C++ effort.

## Current Problem Statement

The bridge exists and is exact, but it is not enough. The remaining bottleneck is no longer “can we enter native code at all”. The real bottleneck is that:

- internal node exact numeric work is still split across Python / Cython / C++ layers
- river-step kernels are still not native enough as a full chain
- per-step boundary crossings and orchestration are still too expensive
- Python still owns too much of the time-step control flow

## Next Optimization Direction

This new branch is for turning the current bridge into a real single-process exact native line by:

1. mapping the exact evolve fullchain precisely
2. profiling the current single-process exact path again from this checkpoint
3. kernelizing the entire internal-node numeric chain in C++
4. kernelizing the current Top 3 evolve hotspots in C++
5. collapsing the time-step loop into a much more native fullchain path
