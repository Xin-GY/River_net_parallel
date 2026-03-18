# Boundary Shell V1 Plan

## Goal

On top of accepted exact baseline `445c2c9`, remove Python-owned external boundary routing/dispatch shell cost without changing:

- boundary formulas
- float64 semantics
- update order
- accumulation order

## Scope

Only target the external `boundary_updater` shell:

- precompile fixed external boundary op order
- prebind river-side method entrypoints
- remove per-step Python node/branch/btype traversal
- keep accepted inflow/outflow formulas unchanged

Out of scope:

- external-boundary-deep numeric ownership
- internal boundary / nodechain refresh deepening
- fullstep / dispatch reshaping
- threads

## Audit Gate

Proceed only if reducible shell/evaluator overhead is still material.

Phase-1 audit outcome:

- `boundary_updater.total = 28.601873 s`
- `boundary_updater.external = 12.427106 s`
- reducible shell/evaluator overhead estimated from 2h cProfile and 40h perf replay:
  - about `8.9 s / 40h`

This passed the go gate, so implementation proceeded.

## Implementation Shape

- add feature flag: `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP=1`
- build and cache a compiled external boundary plan in [Rivernet.py](/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1/handoff_network_model_20260312/Rivernet.py)
- execute the plan in fixed order from [cython_cpp_bridge.pyx](/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1/handoff_network_model_20260312/cython_cpp_bridge.pyx)
- attach optional callable metadata in [Islam.py](/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1/handoff_network_model_20260312/Islam.py)

## Final Constraint Learned During Validation

Shared-source batching looked valid on 10m / 2h but drifted on 40h exact compare. Final v1 therefore keeps:

- deep routing/method ownership
- fixed-order plan execution

but falls back to:

- per-op original boundary callable evaluation

to preserve exactness.
