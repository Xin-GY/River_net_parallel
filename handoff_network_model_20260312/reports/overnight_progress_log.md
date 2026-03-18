# Overnight Progress Log

## Phase 0

- Created continuation branch `feature/cpp-exact-after-assemble-source-deep-v1` from accepted exact candidate `445c2c9`.
- Created dedicated worktree `/tmp/feature_cpp_exact_after_assemble_source_deep_v1`.
- Recorded clean preflight status and branch layout.
- Confirmed this worktree starts without local edits or untracked outputs.
- Confirmed `Caculate_source_term_2` is still a Python per-cell loop on the accepted path and that no source-deep native feature flag exists yet.

## Phase 1

- Read the accepted assemble/global-CFL reports plus the boundary-shell and assemble-threads no-go reports.
- Rechecked the accepted path ownership for `Caculate_source_term_2`.
- Verified from fresh 2h cProfile that source-stage Python time is dominated by repeated `get_DEB_by_area` table dispatch and per-interface Python ownership, not by a native kernel.
- Used the current accepted branch's own 40h stage breakdown to rank `source` against `update_cell`, `assemble`, `boundary_updater`, and `nodechain`.
- Recorded a single continuation decision: proceed with source-term deepening, because it is the cleanest remaining non-nodechain / non-boundary exact ownership gap.

## Phase 2

- Added a dedicated serial exact source-deep feature flag: `ISLAM_CPP_USE_SOURCE_DEEP=1`.
- Added a precompiled source plan that reuses the accepted left/right cross-section table layout.
- Moved the per-interface source loop, DEB lookup, denominator clip handling, and `friction_source` write-back into a native kernel.
- Kept the accepted Python fallback path unchanged when the new flag is off.
- Rebuilt the Cython/C++ extensions and verified imports plus Python syntax.

## Phase 3

- Ran 10m baseline vs candidate with the local no-`h5netcdf` exact harness.
- 10m strict compare passed with:
  - `cfl_history.csv` rows `182 / 182`
  - `internal_node_history.csv` rows `181 / 181`
  - `global_dt max_abs = 0.0`
- Ran 2h baseline vs candidate with the same harness.
- 2h strict compare passed with:
  - `cfl_history.csv` rows `1483 / 1483`
  - `internal_node_history.csv` rows `1482 / 1482`
  - `global_dt max_abs = 0.0`
- Ran 40h baseline vs candidate with the same harness.
- 40h strict compare passed with:
  - `cfl_history.csv` rows `29784 / 29784`
  - `internal_node_history.csv` rows `29783 / 29783`
  - `global_dt max_abs = 0.0`
- Same-harness 40h performance improved from `39.178308 s` to `34.265936 s`.
- Historical accepted 40h gate improved from `47.053824 s` at `445c2c9` to `34.265936 s` on this branch.

## Phase 4

- Rechecked whether any C++ threads experiment should follow immediately.
- Conclusion: do not enter threads now.
- `assemble` and `source` are both smaller after the new accepted candidate, while the remaining raw top costs are still `nodechain / boundary_updater`, which remain tightly entangled with already-rejected exact families.

## Phase 5

- Updated the benchmark, speed, error, and final recommendation reports.
- Prepared the branch for a final source-deep candidate checkpoint if the modified source files and reports are committed together.
