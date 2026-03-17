# C++ Rectangular Roe Flux Deep Before / After

## Acceptance Gate

The new path was tested with:

- `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

and the rest of the accepted exact configuration unchanged.

Strict compare:

- 10m: `allclose = true`
- 2h: `allclose = true`
- 40h: `allclose = true`

## Full-Case Result

Compared with the accepted exact checkpoint `9535623`:

- 40h `evolve/model time`: `91.329929 s -> 65.237010 s`
- improvement: `28.57%`
- 40h strict compare: pass

This meets the branch-family acceptance rule.

## Local Reaudit Replay vs New Candidate

The fresh clean-worktree replay of `9535623` was slower than the historical accepted branch record, but it is still useful for before/after ownership accounting.

| Case | Fresh re-audit replay | New candidate | Speedup |
| --- | ---: | ---: | ---: |
| 10m | 1.233370 s | 0.912919 s | 1.35x |
| 2h | 9.695405 s | 6.680291 s | 1.45x |
| 40h | 101.177666 s | 65.237010 s | 1.55x |

## Historical Accepted Checkpoint vs New Candidate

| Case | Accepted checkpoint `9535623` | New candidate | Speedup |
| --- | ---: | ---: | ---: |
| 10m | 0.667691 s | 0.912919 s | 0.73x |
| 2h | 5.103571 s | 6.680291 s | 0.76x |
| 40h | 91.329929 s | 65.237010 s | 1.40x |

The short cases regressed against the historical accepted record, but the full 40h gate case improved very substantially and remained exact.

## 40h Blocker Delta

### Against the fresh re-audit replay

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `river_step.flux` | 42.333267 s | 4.547068 s | -37.786199 s |
| `river_step.assemble` | 7.132460 s | 6.854175 s | -0.278285 s |
| `river_step.update_cell` | 4.027083 s | 3.574104 s | -0.452979 s |
| `nodechain.total` | 38.318935 s | 41.519373 s | +3.200438 s |
| `boundary_updater.total` | 36.705355 s | 39.055534 s | +2.350179 s |
| `dt_update.global_cfl` | 3.778728 s | 4.038309 s | +0.259581 s |

### Against the accepted historical checkpoint

| Metric | Accepted `9535623` | After | Delta |
| --- | ---: | ---: | ---: |
| `river_step.flux` | 39.820271 s | 4.547068 s | -35.273203 s |
| `nodechain.total` | 35.837393 s | 41.519373 s | +5.681980 s |
| `boundary_updater.total` | 33.800367 s | 39.055534 s | +5.255167 s |
| `river_step.assemble` | 5.721883 s | 6.854175 s | +1.132292 s |
| `river_step.update_cell` | 2.571169 s | 3.574104 s | +1.002935 s |

## Interpretation

- the gain is real and comes almost entirely from cutting the rectangular Roe-flux ownership cost
- `bridge.python_crossings` stayed unchanged at `297830`
- so this is not a dispatch-shape win
- after this change, the main remaining first-order blocker is no longer flux; it shifts back to `boundary_updater / nodechain`
