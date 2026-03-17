# Accepted External Boundary Deep Recheck

## Scope

- Base accepted exact checkpoint: `9a7c094`
- Worktree: `/tmp/feature_cpp_exact_accepted_reaudit_after_rectflux`
- Focused blocker: external boundary ownership only
- Excluded on purpose: refresh deep, residual/Jacobian deep, fullstep, dispatch reshaping, build flags, FAST, multiprocessing

## Variants Tested

### 1. Full external deep

Flags:

- `ISLAM_USE_CYTHON_EXTERNAL_BOUNDARY_DEEP=1`

Results:

- 10m: exact compare passed, `0.8353183269500732 s`
- 2h: exact compare passed, `6.006876707077026 s`
- 40h: `54.386069536209106 s`
- 40h strict compare: failed

Failure shape:

- `cfl_history.csv`: `29784 -> 29811` rows
- `internal_node_history.csv`: `29783 -> 29810` rows
- first divergence at row `3944`, time `19749.31640625 s`
- first differing field:
  - `river13`
  - baseline `5.245466232299805`
  - candidate `5.245466709136963`
  - delta `4.76837158203125e-07`

### 2. Inflow-only external deep

Flags:

- `ISLAM_USE_CYTHON_EXTERNAL_BOUNDARY_INFLOW_DEEP=1`
- `ISLAM_USE_CYTHON_EXTERNAL_BOUNDARY_OUTFLOW_DEEP=0`

Results:

- 10m: exact compare passed, `0.801490068435669 s`
- 2h: exact compare passed, `6.095313787460327 s`
- 40h: `54.4336314201355 s`
- 40h strict compare: failed

Failure shape:

- `cfl_history.csv`: `29784 -> 29659` rows
- `internal_node_history.csv`: `29783 -> 29658` rows
- first divergence at row `3944`, time `19749.31640625 s`
- first differing field:
  - `river13`
  - baseline `5.245466232299805`
  - candidate `5.245466709136963`
  - delta `4.76837158203125e-07`

## What Was Isolated

- Full deep and inflow-only fail at the same first divergence row and same first differing field.
- That isolates the long-horizon drift to the inflow deep path, not the outflow path.

## What Was Ruled Out

Boundary interpolation itself is not the drift source.

Cross-check performed:

- compared Python lambda boundary values vs native-meta exact evaluation
- nodes checked: `n1..n7`, `n14`
- times checked:
  - targeted late times around `39.95h` to `40.05h`
  - all times from accepted 40h `cfl_history.csv`

Observed mismatch:

- max absolute difference: `1.7763568394002505e-15`

Conclusion:

- the drift is downstream of value evaluation
- the likely source is call-path ownership around the inflow `InBound_In_Q2` chain, not interpolation math

## Performance Context

Even though the path is not acceptable for exact use, the speed signal is real:

- full deep 40h model time: `54.386069536209106 s`
- inflow-only 40h model time: `54.4336314201355 s`
- accepted exact baseline reference for this round: `65.23701047897339 s`

Related 40h perf counters:

### Full deep

- `boundary_updater.external = 10.616464996128343`
- `boundary_updater.total = 30.225709356716834`
- `nodechain.total = 38.708901008125395`

### Inflow-only

- `boundary_updater.external = 9.898832874489017`
- `boundary_updater.external.deep_inflow_hits = 29658`
- `boundary_updater.total = 31.438109655166045`
- `nodechain.total = 38.59976850345265`

## Decision

No new accepted exact result from this blocker in its current implementation form.

Status:

- keep external-boundary-deep code as experimental only
- do not upgrade accepted exact configuration
- do not commit this path as an accepted checkpoint

## Next Best Single Direction

Because this blocker is now evidence-backed no-go for exact acceptance in its current form, the next single blocker should be chosen from the fresh accepted exact path excluding external-boundary deep variants.

Most likely next point:

- `Assemble_Flux_2` ownership pushdown

Reason:

- still a real 40h cost
- not part of the rejected refresh/fullstep/build-flag family
- not the same as the rejected external-boundary deep path
