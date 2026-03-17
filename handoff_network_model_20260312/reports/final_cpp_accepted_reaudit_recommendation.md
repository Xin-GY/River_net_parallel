# Final CPP Accepted Reaudit Recommendation

## Result

This round **did** find a new accepted exact candidate.

## New Accepted Candidate

Base:

- start checkpoint: `9535623`

New addition:

- `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

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
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## Gate Verdict

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h `allclose`: `true`
- 40h `evolve/model time`: `91.329929 s -> 65.237010 s`

This is a clear accepted exact improvement.

## Current Top 1 Blocker

### Before this round

The fresh audit showed the accepted path's Top 1 blocker was:

- remaining Python ownership in **rectangular Roe flux**

### After this round

The biggest remaining first-order blocker is now back to:

- `boundary_updater / nodechain`

More specifically:

- `nodechain.total = 41.519373 s`
- `boundary_updater.total = 39.055534 s`
- `nodechain.apply_and_boundary_closure = 16.946484 s`

## What Is Already Substantially Native-Owned

- nodechain deep apply
- nodechain deep commit
- general-HR deep Roe flux
- rectangular-HR deep Roe flux
- face UC
- Roe matrix
- assemble
- update-cell exact kernel

## What Is Still Mixed Ownership

- boundary-updater shell
- nodechain tail orchestration around refresh/commit exposure
- source-term stage
- global CFL / dt reduction

## What Not To Reopen

These remain rejected or not justified:

- refresh deep
- residual/Jacobian deep
- fullstep loop
- build-flag experiments
- `-march=native`
- dispatch / bridge reshaping

## Recommendation

Upgrade this rectangular Roe-flux deep path as the new accepted exact candidate for this branch family.

If we continue from here, the next round should **not** scatter across many ideas again. It should start with a fresh audit on this new `65.237010 s` baseline and choose exactly one point from:

1. nodechain apply/closure tail, only if the implementation shape is materially different from the rejected refresh-deep routes
2. global CFL / dt reduction ownership
3. source-term ownership
