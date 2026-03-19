# Overnight Progress Log

## Phase 0

- Created clean continuation branch `feature/cpp-exact-after-source-riverthreads-v2-clean` from the accepted exact baseline `c92a3ca`.
- Used dedicated worktree `/tmp/feature_cpp_exact_after_source_riverthreads_v2_clean`.
- Recorded preflight branch layout and source-edit scope.
- Locked the round to a deterministic C++ thread runtime only; no nodechain, boundary shell, refresh, or threads-on-rejected-families work was allowed in scope.

## Phase 1

- Re-audited the accepted serial evolve order in `cython_cpp_bridge.pyx` and used it as the exact threaded stage order.
- Verified the v1 drift explanation: the old prototype deviated from the accepted path by using per-river `Caculate_CFL_time_for_river_net()` instead of the accepted `GLOBAL_CFL_DEEP` kernel path.
- Chose to preserve only the safe prototype idea: compiled kernel wrappers can run without Python hot-loop dispatch.

## Phase 2

- Added a native persistent `std::thread` stage-barrier runtime in `cpp/evolve_core.*`.
- Added deterministic contiguous worker ownership in canonical `_river_edges` order.
- Kept main-thread ownership for:
  - `Update_boundary_conditions`
  - internal-node history recording
  - output writing
  - final `DT` decision
- Added compiled per-river plan preparation in `cython_river_kernels.pyx` for:
  - update-cell
  - source
  - flux
  - face-UC / Roe-matrix / CFL raw array access
- Rewired `cython_cpp_bridge.pyx` to call the new native threaded runtime instead of the earlier Python futures-per-stage path.

## Phase 3

- Rebuilt the Cython/C++ extensions successfully.
- Ran 10m exact gate against the accepted serial baseline for thread counts `1 / 2 / 4 / 8 / 14`.
- Restored exactness for the threaded path:
  - all five thread counts passed strict compare
  - `cfl_history.csv` matched exactly
  - `internal_node_history.csv` matched exactly
  - saved outputs matched exactly

## Phase 4

- Benchmarked 10m model time and wall time for serial and all exact thread counts.
- Observed that none of the exact threaded cases beats serial:
  - serial: `4.83 s`
  - threaded-1: `5.02 s`
  - threaded-2: `4.99 s`
  - threaded-4: `5.20 s`
  - threaded-8: `4.99 s`
  - threaded-14: `4.91 s`
- Stopped before 2h because the speed gate was not met at 10m.

## Phase 5

- Wrote implementation, compare, before/after, and final recommendation reports.
- Preserved this branch as an exact threaded prototype below the speed gate.
- Kept the accepted exact baseline unchanged at `feature/cpp-exact-after-assemble-source-deep-v1@c92a3ca`.
