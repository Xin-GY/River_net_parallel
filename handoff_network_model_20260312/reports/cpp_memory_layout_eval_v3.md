# C++ Memory Layout Eval v3

## Status

No new memory-layout refactor was accepted in this continuation branch.

Reason:

- the immediate post-stage-3 work was spent on:
  - documenting the rejected refresh-deep path
  - rechecking residual/fullstep go-no-go
  - evaluating safe build flags
- no higher-confidence SoA/workspace refactor was ready that could be validated within the same exact-only continuation window

## Current state

The branch already benefits from earlier accepted ownership pushdown:

- deep nodechain apply ownership
- deep nodechain commit ownership
- deep Roe flux ownership
- native face/roe/update/assemble kernels already in accepted exact config

The remaining layout opportunities are now narrower and should be tied to a specific dominant hotspot, not done speculatively.

## Next worthwhile layout targets

If this line continues, the next layout-focused candidates should be:

1. persistent workspace reuse around nodechain tail arrays
2. tighter write-back layout for final apply / commit buffers
3. deeper ownership of refresh-related state arrays only if an exact path with real 40h upside is found

## Decision

No memory-layout-only change is accepted from this round.
