# Boundary Shell V1 Branch Layout

## Source Of Truth

- accepted exact source branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- accepted exact source commit: `445c2c9`
- accepted exact source result: `40h evolve/model time = 47.05382442474365 s`
- note: `main` branch index is stale and still points to an older accepted exact checkpoint; it is informational only for this round

## Continuation Layout

- continuation branch: `feature/cpp-exact-after-assemble-boundary-shell-v1`
- continuation worktree: `/tmp/feature_cpp_exact_after_assemble_boundary_shell_v1`
- accepted source worktree reference: `/tmp/feature_cpp_exact_after_globalcfl_assemble_reaudit_v2`

## Scope Lock

This continuation only targets:

- `boundary_updater` external routing / dispatch shell
- accepted external boundary path only
- serial exact ownership pushdown only

This continuation explicitly excludes:

- external-boundary-deep numerical ownership
- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping
- build-flag experiments
- FAST mode
- C++ threads

## Local Generated Artifacts To Exclude From Commits

Current local generated artifacts in this worktree include:

- generated extension sources:
  - `cython_cross_section.c`
  - `cython_node_iteration.c`
  - `cython_river_kernels.cpp`
  - `cython_cpp_bridge.cpp`
- built shared objects:
  - `cython_cross_section.cpython-311-x86_64-linux-gnu.so`
  - `cython_node_iteration.cpython-311-x86_64-linux-gnu.so`
  - `cython_river_kernels.cpython-311-x86_64-linux-gnu.so`
  - `cython_cpp_bridge.cpython-311-x86_64-linux-gnu.so`
- local audit artifacts:
  - `reports/boundary_shell_v1_2h_audit_summary.json`
  - `reports/boundary_shell_v1_2h_audit_perf.json`
  - `reports/boundary_shell_v1_2h_audit.prof`
  - `reports/boundary_shell_v1_40h_audit_summary.json`
  - `reports/boundary_shell_v1_40h_audit_perf.json`
  - `result/boundary_shell_v1_2h_audit/*`
  - `result/boundary_shell_v1_40h_audit/*`

These remain local-only and must stay out of source commits.
