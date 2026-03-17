# Final C++ Nodecommit Refresh Recommendation

## Recommendation

Do **not** upgrade this continuation branch to a new accepted exact baseline.

The accepted exact checkpoint remains:

- `9535623` `perf: deepen exact nodechain commit ownership (+0.8% 40h evolve)`

Its accepted 40h evolve/model time is:

- `91.32992911338806 s`

## Why no new accepted candidate emerged

### 1. Final apply / state commit deeper ownership

This was already the accepted win embodied by `9535623`.

### 2. `_refresh_cell_state` deeper ownership

Tested in two ways:

- inline Cython refresh:
  - faster
  - not exact
- conservative single-cell C++ exact refresh:
  - exact
  - substantially slower

Conclusion:

- no accepted path from this direction in the current form

### 3. Residual / Jacobian

Rechecked and rejected for now:

- too small a share of 40h to justify immediate deeper work

### 4. Fullstep loop

Rechecked and rejected for now:

- previous branch-family evidence already showed short-case wins but 40h regression
- current profile still points to larger ownership hotspots than crossing shape alone

### 5. Build flags

`-march=native` was tested and rejected:

- 10m and 2h exact compares failed badly
- step count exploded, so this is not an acceptable exact optimization

## What is still native-owned vs not fully native-owned

### Already substantially native-owned

- nodechain apply and fast closure core
- nodechain deep apply ownership
- nodechain deep commit ownership
- Roe flux deep ownership
- face-UC / Roe matrix / update-cell / assemble exact kernels in accepted config

### Still not a good accepted next step from this round

- `_refresh_cell_state` deeper ownership
- residual / Jacobian deeper ownership
- fullstep native loop reshaping

## Best next 3 directions

1. Re-open only a **higher-confidence** exact ownership push where 40h profile shows a first-order blocker, not a tail cost.
2. Investigate whether a different exact refresh strategy can avoid the C++-compiled `cython_node_iteration` slowdown while still removing Python-owned refresh cost.
3. Revisit deeper ownership only where it can be shown to preserve the accepted step schedule; otherwise stop before implementation.

## Bottom line

This round produced useful negative knowledge and safer build controls, but no faster accepted exact replacement for `9535623`.
