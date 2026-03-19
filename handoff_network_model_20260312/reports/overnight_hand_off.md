# Overnight Hand Off

## Current Branch

- branch: `feature/cpp-exact-after-source-riverthreads-v2-clean`
- base accepted branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- base accepted commit: `c92a3ca`
- current branch status: exact threaded prototype below speed gate

## What This Round Did

- started cleanly from the accepted exact baseline `c92a3ca`
- did not continue on the older prototype branch `feature/cpp-exact-after-source-riverthreads-v1`
- replaced the previous Python threadpool orchestration with a native persistent `std::thread` stage-barrier runtime
- kept `boundary_updater`, nodechain, internal-node history recording, output writing, and final `DT` ownership on the main thread
- threaded only the river-local accepted stages:
  - `face_uc`
  - `roe_matrix`
  - `source`
  - `flux`
  - `assemble`
  - `update_cell`
  - river-local CFL candidate computation

## Exact Repair

The main v1 numerical mismatch was partly caused by a CFL code-path mismatch. V1 used per-river `Caculate_CFL_time_for_river_net()` instead of the accepted exact `GLOBAL_CFL_DEEP` path.

V2 repaired this by:

- reusing `compute_river_cfl_candidate_exact`
- storing candidates in fixed river order
- merging the global minimum on the main thread in that same fixed order

After this repair, the threaded path became exact at 10m for every tested thread count.

## 10m Exact Gate Status

Baseline:

- `result/riverthreads_v2_clean_serial_10m`
- model time: `4.83 s`
- wall time: `25.779418 s`

Threaded results:

- threaded-1: model `5.02 s`, wall `27.481741 s`, strict compare pass
- threaded-2: model `4.99 s`, wall `25.804064 s`, strict compare pass
- threaded-4: model `5.20 s`, wall `27.570873 s`, strict compare pass
- threaded-8: model `4.99 s`, wall `25.792615 s`, strict compare pass
- threaded-14: model `4.91 s`, wall `26.685991 s`, strict compare pass

All compare runs reported:

- `cfl_history.csv` identical
- `internal_node_history.csv` identical
- saved outputs identical
- `allclose = true`

## Why This Is Not A New Accepted Candidate

The plan required two things:

1. exactness
2. real speedup

This branch achieves the first and fails the second. No exact thread count beats the serial 10m baseline, so the branch does not qualify for 2h or 40h escalation.

## Current Accepted Baseline

The accepted exact baseline remains unchanged:

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: `c92a3ca`
- 40h exact evolve/model time: `34.26593613624573 s`

## Recommended Interpretation

Treat this branch as:

- a successful exact repair of the earlier thread prototype
- useful evidence that deterministic river-local threading is numerically feasible
- not yet a performance win on the current network

## Local State

Keep generated artifacts out of source commits:

- `*.so`
- generated `*.c` / `*.cpp`
- `reports/riverthreads_v2_clean_*_summary.json`
- `reports/riverthreads_v2_clean_*_compare.json`
- `reports/riverthreads_v2_clean_*_stdout.log`
- `result/riverthreads_v2_clean_*`
