# C++ River Threads V2 Clean Implementation

## Goal

This round rebuilds the per-river threading experiment from the true accepted exact baseline `c92a3ca` and replaces the old Python threadpool orchestration with a deterministic native runtime. The target is not to thread the whole network. Only river-local accepted stages are threaded, while `boundary_updater`, internal-node recording, output writing, and final `DT` ownership remain on the main thread.

## Accepted Serial Order Locked In

The threaded path was audited and aligned to the accepted serial stage order:

1. `Set_global_time_step`
2. `Update_boundary_conditions`
3. `_record_internal_node_history_current_state`
4. `face_uc`
5. `roe_matrix`
6. `source`
7. `flux`
8. `assemble`
9. `update_cell`
10. `Save_step_result_net`
11. `global_cfl`

Threaded execution only covers the river-local block from `face_uc` through river-local CFL candidate computation. Everything else remains serial and in the same top-level order as the accepted path.

## Runtime Structure

The previous `ThreadPoolExecutor`-per-stage orchestration was not reused. Instead, a persistent `std::thread` runtime was added in `cpp/evolve_core.*`.

Key properties:

- fixed worker ownership
- contiguous river chunks in canonical `_river_edges` order
- main thread participates as worker slot 0
- stage barriers implemented with `mutex + condition_variable`
- no dynamic scheduling
- no unordered reductions
- no nodechain or boundary ownership moved into worker threads

`ISLAM_CPP_THREADS=0` keeps the accepted serial path unchanged. `ISLAM_CPP_THREADS=1` now activates the native threaded path, with worker count controlled by `ISLAM_CPP_N_THREADS`.

## Compiled Per-River Plans

Before threaded execution begins, one compiled per-river plan set is prepared for the already-accepted local kernels:

- update-cell plan
- source plan
- flux mode selection and plan
- raw array and pointer access for `face_uc`, `roe_matrix`, and CFL

This removes Python method dispatch from the hot worker loop. The worker runtime invokes existing accepted compiled kernels directly.

## Exact Repair Relative To V1

The first v1 prototype drift was partly caused by a code-path mismatch in CFL ownership. It replaced the accepted `GLOBAL_CFL_DEEP` path with per-river `Caculate_CFL_time_for_river_net()`, which is not the accepted serial exact path.

V2 repairs this by:

- reusing the accepted exact kernel `compute_river_cfl_candidate_exact`
- storing one candidate per river in fixed river order
- merging the global minimum on the main thread in that same fixed order

This keeps the CFL decision path aligned with the accepted serial semantics.

## Stage Semantics Preserved

The threaded path does not change:

- numerical formulas
- float64 / float32 usage relative to the accepted path
- stage barrier order
- river traversal order
- reduction ordering for global CFL

To match accepted serial behavior, the flux stage still clears the same river-local temporary arrays before compiled flux execution. Assemble and update-cell continue to use the same accepted compiled plans and write-back ordering.

## Outcome Of The Implementation

This implementation successfully repaired the earlier exactness issue:

- threaded `1 / 2 / 4 / 8 / 14` all pass 10m strict compare against serial
- `cfl_history.csv` remains identical
- `internal_node_history.csv` remains identical
- saved outputs remain identical

However, the runtime does not yet clear the speed gate. At 10m, every tested thread count remains slightly slower than the accepted serial baseline. Therefore the branch is preserved as an exact experimental prototype, not a new accepted candidate.
