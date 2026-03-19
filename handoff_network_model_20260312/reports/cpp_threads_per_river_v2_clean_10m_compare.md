# C++ River Threads V2 Clean 10m Compare

## Compare Setup

- baseline: `result/riverthreads_v2_clean_serial_10m`
- tolerance: `rtol = 1e-12`, `atol = 1e-12`
- compare runner: repository-native `tools/compare_results.py`

## Results

| candidate | strict compare | 40h allclose field equivalent in compare json | note |
| --- | --- | --- | --- |
| `threaded-1` | pass | `allclose = true` | first exact repair target |
| `threaded-2` | pass | `allclose = true` | exact |
| `threaded-4` | pass | `allclose = true` | exact |
| `threaded-8` | pass | `allclose = true` | exact |
| `threaded-14` | pass | `allclose = true` | exact |

## What Changed Relative To V1

The threaded path no longer drifts in 1-thread mode. The key repair was to stop using per-river `Caculate_CFL_time_for_river_net()` as the threaded CFL path and instead reuse the accepted exact `GLOBAL_CFL_DEEP` kernel logic through `compute_river_cfl_candidate_exact`, followed by fixed-order serial merge.

## Gate Outcome

The 10m exact gate is satisfied for all tested thread counts, but the speed gate is not. Since none of the exact thread counts beats the serial baseline at 10m, this round stops before 2h and 40h.
