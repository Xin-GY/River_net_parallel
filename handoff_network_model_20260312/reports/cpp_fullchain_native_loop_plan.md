# C++ Fullchain Native Loop Plan

## Goal

Reduce the remaining per-step Python orchestration cost after the accepted nodechain wrapper-bypass improvement.

## Problem After Phase 3

Even after the exact nodechain wrapper bypass, the bridge still performs this pattern every step:

1. enter boundary updater
2. return to Python network shell
3. call Python network wrappers for each river phase
4. each wrapper fans out again over all rivers
5. return to the bridge
6. call Python network wrapper for CFL reduction

This keeps the time loop exact, but still leaves a large amount of pure orchestration overhead inside:

- `call_river_function_by_name`
- repeated phase wrapper dispatch
- repeated wrapper-level cache checks

## Phase-5 Strategy

Without changing any numeric kernels, move the step orchestration one layer deeper:

- keep the bridge as the owner of the timestep loop
- let the bridge iterate `net._river_edges` directly for the per-river phases
- preserve exactly the same river order as the baseline
- preserve exact `dt` semantics by keeping:
  - original object-valued `DT`
  - original `min(dt_list)` reduction order

## What Changes

When `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=1`:

- `Set_global_time_step(...)` is replaced by direct iteration over cached river objects
- `Caculate_face_U_C_net()` wrapper is bypassed
- `Caculate_Roe_matrix_net()` wrapper is bypassed
- `Caculate_Source_term_net()` wrapper is bypassed
- `Caculate_Roe_flux_net()` wrapper is bypassed
- `Assemble_flux_net()` wrapper is bypassed
- `Update_cell_property_net()` wrapper is bypassed
- `Save_step_result_net()` wrapper is bypassed
- `Caculate_global_CFL()` wrapper is bypassed, while preserving exact reduction semantics

## What Does Not Change

- internal node solve math
- river-step numeric kernels
- output format
- step count
- float64 semantics
- accepted fallback route when the bridge-direct flag is off

## Risk To Control

The main exactness risk in this phase is not the river kernels themselves, but `dt` ordering:

- converting candidate dt values to Python `float` too early changes rounding
- changing `min(...)` reduction semantics changes future steps

That is why this phase explicitly preserves:

- object-valued `dti`
- `min(dt_list)` on the original objects
- the same river traversal order as the Python network shell
