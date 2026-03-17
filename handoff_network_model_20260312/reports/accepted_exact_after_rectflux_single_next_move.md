# Accepted Exact Single Next Move

## Chosen direction

`boundary_updater.external` deeper exact ownership push

More specifically:

- prebind external boundary metadata and branch plans
- move exact scalar boundary evaluation off the Python callable chain
- keep external boundary dispatch in a native loop
- preserve current `InBound_In_Q2` / `InBound_In_Q` / `OutBound_*` semantics and order

## Why this is the current best next move

It is the strongest remaining first-order blocker with clear Python ownership:

- 40h `boundary_updater.external = 16.212713 s`
- 2h `Update_external_boundary_conditions_V2 = 1.838 s`
- 2h `InBound_In_Q2 = 1.180 s`
- 2h `get_boundary_value = 0.548 s`
- 2h `PersistentLinearInterpolator.__call__ = 0.507 s`
- 2h `q_boundary_value = 0.468 s`

This is a large exact chain that still pays Python cost every step, every boundary,
and every river dispatch.

## Why this is not a repeat of rejected directions

It is not:

- `_refresh_cell_state` deeper ownership
- residual / Jacobian deeper push
- fullstep loop / dispatch reshaping
- build-flag experimentation
- FAST / approximate routes

Those routes either already failed or are explicitly out of scope.  
This move targets a different chain: external exact boundary evaluation and dispatch.

## Expected cost addressed

Primary target:

- `boundary_updater.external = 16.212713 s` on 40h

The realistic expectation is not to erase the entire bucket, because the numerical
boundary update methods themselves still execute. But the Python-owned part of:

- boundary dict lookup
- lambda call
- scalar interpolator call
- per-node dispatch

is large enough that a net 40h gain is realistic.

## Exact risk points

- must reproduce `PersistentLinearInterpolator` scalar interpolation exactly
- must preserve cyclic / constant / direct series semantics
- must preserve external boundary node order and river dispatch order
- must not reorder `InBound_In_Q2` / `OutBound_*` calls
- must preserve float64 evaluation order and write-back order

## Rollback strategy

- keep the new path behind a feature flag
- if any unsupported boundary metadata is seen, fall back to the existing Python path
- if 10m / 2h / 40h strict compare fails or 40h has no net gain, disable the flag and
  keep `9a7c094` as the accepted exact baseline
