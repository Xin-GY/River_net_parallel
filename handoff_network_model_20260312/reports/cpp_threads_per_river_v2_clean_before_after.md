# C++ River Threads V2 Clean Before / After

## Baseline

- accepted baseline branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- accepted baseline commit: `c92a3ca`
- local comparison case: 10 minutes
- baseline case name: `riverthreads_v2_clean_serial_10m`

## 10m Performance Table

| mode | model time (s) | wall time (s) | delta vs serial model (s) | speedup vs serial model |
| --- | ---: | ---: | ---: | ---: |
| serial | 4.83 | 25.779418 | 0.00 | 1.000x |
| threaded-1 | 5.02 | 27.481741 | +0.19 | 0.962x |
| threaded-2 | 4.99 | 25.804064 | +0.16 | 0.968x |
| threaded-4 | 5.20 | 27.570873 | +0.37 | 0.929x |
| threaded-8 | 4.99 | 25.792615 | +0.16 | 0.968x |
| threaded-14 | 4.91 | 26.685991 | +0.08 | 0.984x |

## Exactness Summary

All tested thread counts pass 10m strict compare against the serial baseline:

- threaded-1: pass
- threaded-2: pass
- threaded-4: pass
- threaded-8: pass
- threaded-14: pass

For every passed case:

- `cfl_history.csv` row counts match exactly
- `internal_node_history.csv` row counts match exactly
- `global_dt` remains identical
- saved netCDF outputs remain identical
- compare result reports record `allclose = true`

## Key Interpretation

V2 materially improves on the earlier thread prototype because it restores exactness across all tested thread counts. The remaining blocker is no longer numerical drift. The blocker is speed:

- the best model-time result is `threaded-14 = 4.91 s`
- this is still slower than `serial = 4.83 s`
- therefore the experiment does not qualify for 2h escalation under the stated gate

## Decision

This branch should be preserved as:

- deterministic exact threaded prototype
- below speed gate
- not a new accepted exact candidate
