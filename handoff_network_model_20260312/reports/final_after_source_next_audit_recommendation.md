# Final After Source Next Audit Recommendation

## Verdict

Keep `feature/cpp-exact-after-assemble-source-deep-v1@c92a3ca` as the accepted exact baseline.

No further exact implementation should start now.

## Direct Answers

### 1. Should the accepted exact baseline remain `c92a3ca`?

Yes.

Nothing in this audit overturns `c92a3ca`, and this round intentionally stops before code changes.

### 2. What is the current raw Top 1 blocker?

Raw Top 1 is still:

- `nodechain.total`
- `boundary_updater.total`

### 3. Does a unique materially new exact-serial candidate exist right now?

No.

The audit result is `none`.

### 4. Why not continue `boundary_shell_v1`, `assemble threads`, or `updatecell_v2`?

- `boundary_shell_v1`: exact shell-only path did not produce same-harness 40h net gain, and grouped evaluator batching is not 40h exact.
- `assemble threads`: deterministic-thread shape is acceptable, but grain size is too small to justify implementation.
- `updatecell_v2`: fresh audit confirms the meaningful update-cell work is already native-owned and the remaining shell is too thin.

### 5. Why not promote `flux` as the next implementation target?

Because the current accepted runtime already uses:

- accepted rectangular-HR deep flux ownership
- accepted general-HR deep C++ flux ownership with a precompiled plan

What remains outside the native kernel is mostly stage orchestration and resets, not a large new ownership gap. That does not clear the bar for a new accepted exact round.

### 6. Should any C++ native threads implementation start now?

No.

The current threads answer remains:

- first deterministic C++ threads object: `none`

### 7. What directions remain explicitly closed?

Do not reopen:

- `_refresh_cell_state` deeper ownership old route
- residual / Jacobian deep
- fullstep / dispatch reshaping
- external-boundary-deep exact family
- boundary shell grouped batching
- boundary shell shell-only continuation
- assemble threads v1
- updatecell_v2 shell continuation
- FAST_MODE
- Python multiprocessing / threading
- `-march=native`
- `-ffast-math`

## Recommendation

Freeze `c92a3ca` as the current accepted exact baseline.

If a future exact-only round is started, it should begin only after someone can articulate one **materially new** nodechain / boundary ownership design that is clearly outside the rejected refresh/fullstep/residual/boundary-batching families.

Until then, the correct action is to stop implementation work and keep the current accepted baseline stable.
