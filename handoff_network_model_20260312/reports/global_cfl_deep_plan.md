# Global CFL Deep Plan

## Goal

Push the full `global CFL / dt reduction` stage from Python/NumPy ownership into native serial ownership, while preserving:

- exact formula
- float32 array semantics inside each river CFL candidate
- fixed river-order merge semantics
- identical `cfl_history.csv` / `internal_node_history.csv`

## Native ownership boundary

The deep path is isolated behind:

- `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`

When enabled:

1. per-river CFL candidate computation runs in `cpp/evolve_core.cpp`
2. `cython_cpp_bridge.pyx` owns the fixed-order loop over prebound river refs
3. the net-level minimum reduction is done in the same native/Cython stage
4. history recording keeps the original river order and field order

## What stays out

- no nodechain changes
- no source-term changes
- no assemble / update-cell changes
- no fullstep reshaping
- no external-boundary-deep logic
- no thread parallelism in this first implementation

## Exactness rules

- keep the river candidate kernel in float32 arithmetic to match current NumPy path
- keep the fixed `_river_edges` ordering for the global reduction
- keep `global_dt` equal to the serial minimum of the same ordered candidate list
- keep history field order:
  - `time`
  - river names in `_river_edges` order
  - `global_dt`
