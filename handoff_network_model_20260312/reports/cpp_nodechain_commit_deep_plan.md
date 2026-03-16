# Nodechain Commit Deep Plan

## Goal

Push the exact nodechain tail further into native ownership by reducing the Python-side work in:

- `final_apply`
- boundary-face state write-back
- downstream consumers that immediately read boundary-face state after node iteration

The target is not to change the nodechain math. The target is to stop paying for Python-owned face-state scatter when the native deep plan already owns the authoritative exact face state.

## Accepted baseline before this step

- branch: `feature/cpp-exact-evolve-nodechain-deepnative`
- accepted commit: `f8f0db0`
- accepted 40h evolve/model time: `92.091939 s`

Relevant 40h nodechain costs before this step:

- `nodechain.total = 36.756061 s`
- `nodechain.apply_and_boundary_closure = 14.925780 s`
- `nodechain.final_apply = 2.637463 s`

## Remaining native gap

After deep apply, the native plan already owns:

- branch-side stage-boundary context
- exact face state produced by `compute_stage_boundary_mainline_fast`
- closure-time face level / area / discharge / width cache

But the accepted path still paid Python-side tail cost because:

- final apply still synchronized cached face state back to Python boundary attributes
- later consumers still read those Python boundary attributes instead of the native cache
- that kept the nodechain tail in a hybrid ownership state

## Planned pushdown

1. Keep exact face-state ownership in `NodeBoundaryDeepPlan` through final apply.
2. Add a read path that lets downstream exact consumers pull boundary-face state directly from the deep plan cache.
3. Only fall back to Python boundary attributes when the deep cache is unavailable or the new feature flag is off.

## Scope

This step only targets:

- `final_apply`
- boundary-face state commit
- immediate post-nodechain reads used by:
  - node residual / Ac helpers
  - internal node history recording
  - node mass residual helpers

This step does **not** attempt to change:

- closure order
- residual / Ac math
- Jacobian / stopping logic
- bridge / dispatch shape
- river-step ownership

## Design

### Native ownership change

In `cython_node_iteration.pyx`:

- introduce a `use_commit_deep` path inside `run_internal_node_iteration_exact(...)`
- keep `NodeBoundaryDeepPlan.face_*` as the source of truth through final apply
- skip `sync_python_boundary_state()` during final apply when `use_commit_deep` is enabled

### Read-side change

In `Rivernet.py`:

- attach left/right deep plans back onto each river object when the nodechain plan is built
- add `_get_boundary_face_state_cached(river, side)`:
  - first try the native deep-plan cache when commit-deep is enabled
  - otherwise fall back to Python boundary-face attributes

### Consumers switched to cached reads

- `Caculate_node_Ac_at_ghost_cell_JPWSPC`
- `_get_node_mass_residual_current_state` helper paths
- `_record_internal_node_history_current_state`

## Exactness guardrails

- keep `float64` semantics
- keep identical loop order and accumulation order
- do not change closure call count
- do not change node iteration stopping logic
- keep Python fallback intact behind a feature flag

## Feature flag

- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`

The flag is only meaningful when:

- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`

## Acceptance rule

Accept only if all of the following hold:

- 10m strict compare passes
- 2h strict compare passes
- 40h strict compare passes
- 40h evolve/model time improves relative to `92.091939 s`
