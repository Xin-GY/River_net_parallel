# nodechain tail native gap ranked

## ranking basis

Ranking is based on:

- current accepted exact 2h replay on this branch
- accepted 40h reference from identical source commit
- direct nodechain timers
- 2h cProfile evidence for remaining Python-owned tail calls

## ranked native gaps

### 1. final_apply / state commit deeper native ownership

Why first:

- `nodechain.final_apply` is still a distinct, measurable block:
  - `0.129647 s` on 2h
  - `2.637463 s` on 40h
- final apply still performs:
  - final exact closure replay
  - Python boundary-face attr scatter through `sync_python_boundary_state()`
  - Python dict update for node level cache
- this is a clean ownership target and directly aligned with the user’s requested priority

### 2. `_refresh_cell_state` deeper exact ownership

Why second:

- cProfile shows `_refresh_cell_state` is the largest remaining Python-owned call near nodechain tail
- accepted deep-apply already removed Python boundary closures and width lookups, so refresh is now the obvious next tail blocker
- however, it is second rather than first because it is more invasive and easier to introduce drift if pushed too aggressively

### 3. residual / Jacobian only if reprofile says it matters again

Why third:

- `nodechain.residual_and_ac` is already tiny:
  - `0.018511 s` on 2h
  - `0.213633 s` on 40h
- this no longer justifies being the next default target

## recommended execution order

1. `final_apply / state commit` deeper native ownership
2. `_refresh_cell_state` deeper exact ownership
3. residual / Jacobian only after a recheck

## no-go items for this round

Do not spend time on:

- dispatch/bridge shape experiments
- multiprocessing or multithreading benchmarks
- FAST_MODE
- approximate node solve routes
- residual/Jacobian pushdown before final apply / refresh ownership is rechecked
