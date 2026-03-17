# Final CPP After Global CFL Recommendation

## Verdict

This round **does** produce a new accepted exact candidate.

## New Accepted Candidate

Base:

- accepted checkpoint: `feature/cpp-exact-accepted-reaudit-next@9a7c094`

New addition:

- `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`

Accepted exact config now becomes:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## Gate Verdict

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h `allclose`: `true`
- 40h `evolve/model time`: `65.237010 s -> 60.743103 s`

This is a clear accepted exact improvement.

## Why this worked

- the full `global CFL / dt reduction` stage was still Python/NumPy-owned in the accepted path
- the new serial native path removed:
  - Python per-river CFL candidate calls
  - Python `dt_list` / `dt_items` construction
  - Python-level minimum reduction
- exact history ordering stayed unchanged, so:
  - `cfl_history.csv`
  - `internal_node_history.csv`
  remained bitwise-identical in the compared outputs

## Why the thread stage was not entered

- after the serial pushdown, `dt_update.global_cfl` fell to `0.728253 s`
- that is no longer a large enough cost center to justify a same-round deterministic threading experiment
- accepted status is therefore based on the serial native path only

## Current first-order blocker

Raw first-order blocker on the new accepted exact path is now back to:

- `boundary_updater / nodechain`

More specifically, on the 40h candidate:

- `nodechain.total = 41.198503 s`
- `boundary_updater.total = 38.832676 s`
- `river_step.assemble = 6.546105 s`

## Next single point, if exact-only work continues

The next round should not reopen:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping
- external-boundary-deep exact
- `-march=native`

The next single point should be one of:

1. a materially new nodechain ownership idea, only if it is clearly different from the rejected refresh/fullstep family
2. otherwise, `Assemble_Flux_2` deeper ownership should be re-audited on top of this new accepted `60.743103 s` baseline

At this point, `global CFL / dt reduction` is no longer the right place to spend the next round.
