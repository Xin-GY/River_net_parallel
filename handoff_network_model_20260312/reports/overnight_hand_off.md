# Overnight Hand Off

## Current Branch

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- head: pending final checkpoint on top of `348aadc`
- true accepted starting point for this round: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2@445c2c9`

## What This Round Did

- Stayed on the true accepted exact baseline `445c2c9`, not the stale `main` index.
- Re-audited only `Caculate_source_term_2`.
- Added a new isolated exact feature flag:
  - `ISLAM_CPP_USE_SOURCE_DEEP=1`
- Kept the accepted serial baseline path unchanged when the new flag is off.
- Moved the source-stage per-interface loop, left/right DEB lookup, denominator clip handling, and `friction_source` write-back into a serial native kernel.

## Exact Gate Status

Used the local no-`h5netcdf` strict-compare harness because this machine could not install `h5netcdf` successfully. The compare thresholds remained:

- `rtol = 1e-12`
- `atol = 1e-12`

and the compared artifacts still included:

- `cfl_history.csv`
- `internal_node_history.csv`
- saved CSV / netCDF outputs

Results:

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h compare: `allclose = true`

## Performance

Historical accepted 40h gate:

- `445c2c9`: `47.05382442474365 s`

Same-harness fresh replay on this branch:

- baseline: `39.17830753326416 s`
- source-deep candidate: `34.26593613624573 s`

This means:

- same-harness 40h A/B gain: `4.912371 s`
- accepted-gate gain vs `445c2c9`: `12.787888 s`

## Stage Impact On Fresh 40h Replay

- `river_step.source`: `1.152433 s -> 0.329018 s`
- `river_dispatch.Caculate_source_term_2.time`: `1.115864 s -> 0.298392 s`
- `river_step.update_cell`: `1.830265 s -> 1.729327 s`
- `river_step.assemble`: `1.697002 s -> 1.597568 s`
- `boundary_updater.total`: `27.429416 s -> 25.179718 s`
- `nodechain.total`: `28.920906 s -> 26.428349 s`

## Current Conclusion

This round does produce a new accepted exact candidate if the modified source files and reports are committed:

- candidate branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- candidate feature flag: `ISLAM_CPP_USE_SOURCE_DEEP=1`
- candidate 40h exact evolve/model time: `34.26593613624573 s`

## Remaining First-Order Blocker

Raw Top 1 remains:

- `nodechain.total`
- `boundary_updater.total`

But the remaining obvious deeper routes there are still close to already-rejected exact families:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping
- boundary grouped-evaluator batching

## Threads Recheck

Do not implement threads yet.

After this round:

- `source` is now too small to be a first threads target
- `assemble` is also smaller than before
- the raw heavy remaining stages are `nodechain / boundary_updater`, which are not currently safe first thread targets

## Local State

Generated artifacts remain untracked and must stay out of the commit:

- `*.so`
- generated `*.c` / `*.cpp`
- `reports/*_summary.json`
- `reports/*_perf.json`
- `reports/*_compare.json`
- `reports/*.prof`
- `result/**`
