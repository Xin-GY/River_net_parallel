# Overnight Progress Log

## 2026-03-18 Phase 0 / Phase 1

- created continuation branch `feature/cpp-exact-after-assemble-boundary-shell-v1` from `445c2c9`
- confirmed this round must use `445c2c9` as the accepted exact baseline even though `main` docs are stale
- rebuilt required local extensions in the new worktree:
  - `cython_cross_section`
  - `cython_node_iteration`
  - `cython_river_kernels`
  - `cython_cpp_bridge`
- reran accepted-path audit on the rebuilt worktree
- produced:
  - `accepted_after_assemble_boundary_shell_v1_preflight_git_status.txt`
  - `accepted_after_assemble_boundary_shell_v1_branch_layout.md`
  - `boundary_shell_v1_hotspot_recheck.md`

Phase-1 verdict:

- go
- `boundary_updater.external` remains the largest clean blocker outside the already-rejected nodechain-deeper families
- proceed to boundary shell deeper ownership pushdown only

## 2026-03-18 Phase 2 / Phase 3

- implemented boundary-shell deep routing under `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP=1`
- first implementation used shared-source evaluator batching
- grouped version passed 10m / 2h but failed 40h exact compare
- narrowed the failure to the grouped evaluator path rather than boundary formula bodies
- repaired the implementation by:
  - keeping the precompiled routing/method plan
  - restoring per-op original callable evaluation
  - restoring original `current_sim_time` callable argument semantics
- reran 10m / 2h / 40h strict compare on the repaired candidate
- final repaired candidate passed all exact gates

Phase-3 verdict:

- exact: yes
- same-harness 40h net gain: no
- keep as documented prototype only
- do not upgrade accepted exact
