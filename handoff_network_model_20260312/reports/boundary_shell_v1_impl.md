# Boundary Shell V1 Implementation

## What Changed

### [Rivernet.py](/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1/handoff_network_model_20260312/Rivernet.py)

- added `use_cpp_boundary_shell_deep`
- added boundary-shell plan cache and invalidation hooks
- invalidated the plan on:
  - river-cache refresh
  - `set_boundary`
  - `update_func`
  - `update_type`
- added `_build_cpp_boundary_shell_plan()`:
  - preserves external node order
  - preserves per-node branch order
  - preserves inflow/outflow dispatch order
  - prebinds exact accepted boundary method entrypoints
- `Update_external_boundary_conditions_V2()` now tries the deep shell executor first when the flag is on

### [cython_cpp_bridge.pyx](/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1/handoff_network_model_20260312/cython_cpp_bridge.pyx)

- added `run_external_boundary_shell_deep(net)`
- walks the precompiled op list in fixed order
- records sub-timers:
  - `boundary_updater.external.shell_eval`
  - `boundary_updater.external.formula_apply`
  - `boundary_updater.external.deep.calls`
  - `boundary_updater.external.deep.ops`
  - `boundary_updater.external.deep.group_count`

### [Islam.py](/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1/handoff_network_model_20260312/Islam.py)

- added optional callable metadata under `__islam_boundary_meta__`
- wired env flag `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP`

## What Was Tried And Rejected Inside V1

First implementation attempt used shared-source batching for:

- seven inflow nodes sharing one hydrograph source
- one outflow node sharing one level source

That grouped version was:

- exact on 10m
- exact on 2h
- not exact on 40h

Observed failure:

- baseline steps: `29783`
- grouped candidate steps: `29810`
- first drift around `23399.751953125 s`

Root cause conclusion:

- not the boundary formula bodies
- not the plan ordering
- the grouped evaluator path itself changed long-horizon exact behavior

## Final Exact V1 Shape

The final exact version keeps the deep shell plan, but disables grouped evaluator reuse:

- each boundary op still evaluates its original callable
- original `current_sim_time` object is passed through to the callable
- shared-source metadata remains attached, but grouped reuse is not used in the accepted exact candidate for this branch

This restored exactness on 10m / 2h / 40h.
