# Source Worktree Dirty Inventory

## Source inspected before branch split

- worktree: `/tmp/feature_cpp_exact_evolve_fullchain`
- branch: `feature/cpp-exact-evolve-fullchain`
- head: `835cf1f`

## Dirty content class summary

- generated native build outputs
  - `cython_cpp_bridge.cpp`
  - `cython_cpp_bridge*.so`
  - `cython_node_iteration*.c/.so`
  - `cython_river_kernels*.c/.so`
- exploratory benchmark summaries not kept in the accepted checkpoint
- exploratory comparison JSON created while validating bridge routing and output cadence

## Why these were not carried into the new branch

- they are reproducible
- they do not change source semantics
- they would pollute the next kernelization line
- this new branch should stay focused on source changes, profiling, and accepted validation outputs only
