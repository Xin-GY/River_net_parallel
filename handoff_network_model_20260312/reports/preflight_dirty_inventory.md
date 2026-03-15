# Preflight Dirty Inventory

Current FAST worktree:

- worktree: `/tmp/overnight_fast_mode_30s`
- branch: `fast-mode-30s`
- HEAD: `367230fe9cf522ecf68bf8b1b7a106fa29055679`

Tracked source files currently have no uncommitted edits:

- `Islam.py`: clean in worktree and index; latest accepted FAST-only refresh controls are already committed.
- `Rivernet.py`: clean in worktree and index; latest FAST-only node refresh and reporting changes are already committed.
- `parallel_river_pool.py`: clean in worktree and index; no outstanding local edits.
- `river_for_net.py`: clean in worktree and index; no outstanding local edits.
- `tools/evaluate_fast_mode.py`: clean in worktree and index; latest FAST evaluation helpers are already committed.

Current dirty state comes from untracked experimental artifacts only:

- `handoff_network_model_20260312/bound`
  - untracked symlink to the shared `bound` directory
- `handoff_network_model_20260312/reports/dt_profile_exact_40h.md`
  - copied exact-side reference report, not committed on FAST branch
- `handoff_network_model_20260312/reports/fast_eval_adaptive_10m.*`
  - retained adaptive experiment outputs
- `handoff_network_model_20260312/reports/fast_eval_adaptive_cfl125_vs_accepted40h.*`
  - retained adaptive 40h evaluation outputs
- `handoff_network_model_20260312/reports/fast_eval_root_iter2_cfl20_dt135_refresh2hold_vs_accepted40h.*`
  - retained intermediate evaluation output
- `handoff_network_model_20260312/reports/sweep_runs/`
  - per-candidate FAST sweep JSON artifacts

Conclusion:

- there are no outstanding uncommitted code edits to the listed source files
- all current dirt is recoverable report or artifact state
