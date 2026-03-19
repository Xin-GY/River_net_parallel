# After Source Next Audit Branch Layout

## Scope

This branch is an audit-only continuation from the true accepted exact baseline:

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: `c92a3ca`

It exists only to decide whether any materially new exact-only candidate remains after `source_deep_v1`.

## Audit Rule

- Default mode for this branch is documentation and design audit only.
- No implementation code should be added on this branch unless the audit first identifies one unique materially new candidate and explicitly justifies a follow-on implementation branch.

## Excluded Generated Artifacts

These artifacts may appear locally during profiling or compare runs and must stay out of commits:

- `*.so`
- generated `*.c`
- generated `*.cpp`
- `reports/*_summary.json`
- `reports/*_perf.json`
- `reports/*_compare.json`
- `reports/*.prof`
- `result/**`
- local links or copied `bound` artifacts

## Current Local State

- worktree path: `/tmp/feature_cpp_exact_after_source_next_audit`
- branch state at creation: clean
- inherited accepted feature set:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
  - `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
  - `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
  - `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - `ISLAM_CPP_USE_ASSEMBLE=1`
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
  - `ISLAM_CPP_USE_ROE_MATRIX=1`
  - `ISLAM_CPP_USE_FACE_UC=1`
  - `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`
  - `ISLAM_CPP_USE_SOURCE_DEEP=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
  - `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`
