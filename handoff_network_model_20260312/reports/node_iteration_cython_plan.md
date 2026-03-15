# Node Iteration Cython Plan

## Goal

Replace the serial internal-node exact orchestration chain with an in-process exact Cython path, without changing:

- physics
- boundary semantics
- update order
- float precision
- accumulation order

This branch does not optimize multiprocessing, IPC, response tables, or approximate node solves.

## New Modules

### `cython_node_iteration.pyx`

Primary exact nodechain module.

Planned responsibilities:

- dense node iteration loops
- dense residual assembly
- dense Ac / denominator assembly
- stopping checks
- exact per-node update loop

### `cython_node_iteration.pxd`

Optional shared declarations for:

- typed structs / enums for side codes
- helper signatures shared with `cython_river_kernels.pyx`

### `cython_river_kernels.pyx`

Second-stage serial evolve hotspot module for non-nodechain Top 3 kernels discovered in profiling.

Likely targets after profiling:

- `Caculate_Roe_Flux_2`
- `Update_cell_proprity2`
- `Caculate_Roe_matrix` or `Caculate_face_U_C`

### `cython_exact_types.pxd`

Optional shared low-level declarations:

- integer codes for left/right side
- integer codes for node update modes
- common `float64` aliases if helpful

### `build_cython_exact_kernels.py`

New build entrypoint.

It should compile:

- `cython_node_iteration`
- `cython_river_kernels` when present

`build_cython_cross_section.py` remains unchanged and still builds the existing cross-section Cython module.

## Python / Cython Split

### Python remains responsible for

- scenario setup in `Islam.py`
- build / import fallback logic
- feature flags
- high-level benchmark harnesses
- final error reporting and drift isolation

### Cython becomes responsible for

- repeated node iteration loops
- dense node residual/Ac accumulation
- exact stopping logic
- serial hotspot outer loops discovered in profiling

## Planned Exact Nodechain API

### Python wrapper in `Rivernet.py`

Add a branch-local flag:

- `ISLAM_USE_CYTHON_NODECHAIN=1`

Wrapper flow:

1. build dense node order once
2. build incident branch plan once
3. prebind branch descriptors
4. call Cython exact nodechain entry point
5. fall back to current Python implementation when unavailable or disabled

### Prebound dense inputs

- `node_names` kept in Python only for reporting
- `node_offsets[int32]`
- `branch_node_index[int32]`
- `branch_river_index[int32]`
- `branch_side_code[int8]`
- `branch_flow_sign[int8]`
- `levels[float64]`
- `residuals[float64]`
- `dz[float64]`

### River-side exact references

Because the boundary closure formulas are already implemented on `River`, the first exact Cython version should prebind:

- Python `River` object array in fixed river order
- integer side codes for each branch
- precomputed boundary layout metadata per branch:
  - ghost index
  - inner index
  - second index
  - whether V2 or V3 closure path is active
- boundary table refs when accessible:
  - target table
  - inner table
  - second table

This preserves semantics while removing network-level dict and traversal overhead first.

## Loop Downshifting Strategy

### Stage A: exact nodechain traversal

Move this whole loop nest into Cython:

- for iteration in `max_iteration`
  - for node in internal nodes:
    - for branch in incident branches:
      - apply exact boundary closure
  - for node in internal nodes:
    - compute residual
  - for node in internal nodes:
    - compute `Ac` or numerical derivative
  - update node levels
  - stopping check

Exactness rule:

- preserve the same node order as `self.internal_nodes`
- preserve the same incident branch order as current `_in_branches_by_node[node]` then `_out_branches_by_node[node]`
- preserve the same residual accumulation order

### Stage B: river hotspot outer loops

After serial profiling, move the Top 3 outer loops into `cython_river_kernels.pyx`.

Most likely:

- per-face flux loop from `Caculate_Roe_Flux_2`
- per-cell refresh loop from `Update_cell_proprity2`
- per-face Roe-matrix or face-state loop depending on measured Top 3

## Maintaining Float64 Exactness

Rules:

- use `float64` only
- no `float32`
- no `prange`
- no OpenMP
- no approximate lookup tables
- no response table
- no predictor approximation
- no reordering of reduction or update passes

Any Cython kernel that drifts must remain behind its own feature flag until isolated.

## Python Fallback Design

Every kernel introduced in this branch must have a Python fallback:

- nodechain:
  - `ISLAM_USE_CYTHON_NODECHAIN`
- hotspot kernels:
  - per-kernel flags such as:
    - `ISLAM_USE_CYTHON_ROE_FLUX`
    - `ISLAM_USE_CYTHON_UPDATE_CELL`
    - `ISLAM_USE_CYTHON_FACE_UC`
    - actual names depend on profiled Top 3

This lets us bisect numerical drift one kernel at a time.

## Build And Validation Path

1. build existing cross-section Cython module
2. build new exact kernel module(s)
3. run 10-minute serial Python baseline
4. enable one kernel at a time
5. compare:
   - `array_equal`
   - `allclose`
   - `max_abs`
   - `max_rel`
   - first mismatch location
6. only after passing 10-minute validation, run long serial benchmark

## Why This Plan Is Worthwhile

The accepted baseline already Cythonizes some local hydraulic formulas. The remaining serial internal-node cost is still dominated by Python orchestration:

- `dict[str, float]`
- node-name keyed lookup
- repeated per-node method dispatch
- repeated incident-branch tuple traversal

So the highest-value exact Cython move is not another tiny formula helper. It is moving the whole node-iteration shell and then the serial Top 3 outer evolve loops into compiled exact kernels.
