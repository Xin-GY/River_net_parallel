# Accepted After Source UpdateCell V2 Branch Layout

## Starting Point

- source branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- source commit: `c92a3ca`
- continuation branch: `feature/cpp-exact-after-source-updatecell-v2`
- continuation worktree: `/tmp/feature_cpp_exact_after_source_updatecell_v2`

## Accepted Baseline For This Round

This round treats `c92a3ca` as the authoritative accepted exact baseline.

The stale `main` branch index was not used as the starting point.

## Phase-0 Cleanliness Check

- worktree status at creation: clean
- local accepted config can be reproduced directly from environment flags
- no preserved boundary-shell / threads / external-boundary variants were carried into this continuation worktree

## Generated Artifacts To Exclude From Commits

Do not commit newly generated local artifacts such as:

- build outputs: `*.so`
- generated Cython emission files outside tracked source: `*.c`, generated `*.cpp`
- benchmark summaries: `reports/*_summary.json`
- perf dumps: `reports/*_perf.json`
- compare outputs: `reports/*_compare.json`
- cProfile dumps: `reports/*.prof`
- result folders: `handoff_network_model_20260312/result/**`
- local links / scratch files

Note:

- tracked source files inside `handoff_network_model_20260312/cpp/*.cpp` are part of the repository and are not “generated artifact” exclusions
- this worktree currently starts without local untracked benchmark outputs
