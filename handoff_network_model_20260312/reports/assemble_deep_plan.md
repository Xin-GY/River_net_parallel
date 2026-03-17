# Assemble Deep Plan

## Goal

Push `Assemble_Flux_2` from a Python-owned stage shell into a more native-owned exact post-flux stage without reopening refresh/fullstep/external-boundary-deep logic.

## Intended Ownership Move

- keep `Update_cell_proprity2()` and rejected refresh-deep paths untouched
- keep existing `ISLAM_CPP_USE_ASSEMBLE=1` path as fallback
- add a deeper flag:
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
- move this stage chain into one native-owned step:
  - conservative flux increment
  - exact Manning post-step
  - conservative dry admissibility
  - write-back to `S/Q/Flux`

## Exact Constraints

- float64 semantics preserved where the accepted path uses them
- no formula changes
- no update-order or accumulation-order changes
- no dispatch reshaping, no refresh-deep reuse, no external-boundary-deep reuse
