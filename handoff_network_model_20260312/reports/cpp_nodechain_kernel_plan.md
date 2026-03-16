# C++ Nodechain Kernel Plan

## Goal

Push the internal-node exact chain deeper into compiled code without changing any numeric semantics and without switching to multiprocessing, threading benchmarks, FAST mode, or approximate node solvers.

## Baseline Problem

Phase-2 profiling on this branch showed:

- `boundary_updater.total`: `4.076405 s` over the corrected 2h perf run
- `nodechain.apply_and_boundary_closure`: `2.771246 s`
- `336020` boundary-closure calls in 2h
- `306380` width lookups in residual/Ac assembly
- `14820` Python/Cython/C++ crossings in 2h

The exact low-level closure math is already compiled, but the nodechain still pays for Python wrapper layers around it.

## Kernelization Strategy

This phase uses a staged approach:

1. keep the accepted exact math unchanged
2. bypass Python boundary wrapper shells where the wrapper only forwards to the exact compiled fast path
3. keep fallback to the original Python boundary wrapper if any blocker prevents the fast route
4. preserve:
   - float64 arithmetic
   - node iteration order
   - branch traversal order
   - final synchronized apply order

## Experiments In This Phase

### Rejected prototype A: direct stage-boundary numeric closure from `cython_node_iteration.pyx`

- intended change:
  - call `compute_stage_boundary_mainline_fast(...)` directly from the nodechain loop
  - bypass `InBound_Fix_level_V3` / `OutBound_Fix_level_V3`
  - commit boundary state directly from the nodechain loop
- outcome:
  - 10m smoke produced a segmentation fault
- status:
  - rejected, kept only as an external patch snapshot

### Rejected prototype B: exact width lookup via prebound table refs

- intended change:
  - replace `cross_section_table.get_width_by_area(section_name, area)` with per-cell table-ref lookup in the nodechain residual/Ac loop
- outcome:
  - numerically tiny but non-zero drift in `internal_node_history.csv`
  - 10m max differences were on the order of `1e-9` for level and `1e-7` for `Q`
- status:
  - rejected for the exact default path

### Accepted phase-3 candidate: wrapper bypass

- implemented change:
  - when `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`, the nodechain loop calls:
    - `river._stage_boundary_fix_level_cython_fast(...)`
  - if that compiled exact closure accepts the state, the nodechain skips:
    - `InBound_Fix_level_V3`
    - `OutBound_Fix_level_V3`
  - if it declines, the nodechain falls back to the original Python wrapper path
- why this is exact:
  - it reuses the same existing exact compiled closure
  - it preserves the same node/branch iteration order
  - it preserves the same fallback path
  - it does not alter Roe flux, update-cell, dt, or output semantics

## Expected Benefit

This phase only targets the nodechain shell. It does not yet collapse the full timestep into a native loop. The realistic expected win is:

- modest but safe speedup in:
  - `boundary_updater.total`
  - `nodechain.apply_and_boundary_closure`
- no change to:
  - step count
  - CFL path
  - river-step kernel semantics

## Next Step After This Phase

If the wrapper-bypass path remains exact on 10m / 2h / 40h and shows a real full-case gain, the next move is:

1. keep it as the accepted nodechain baseline on this branch
2. continue phase 4 on the current Top 3:
   - `Caculate_Roe_Flux_2`
   - `Update_cell_proprity2`
3. then reduce Python/Cython/C++ boundary crossings in the timestep loop itself
