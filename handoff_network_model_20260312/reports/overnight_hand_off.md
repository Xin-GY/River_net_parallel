# Overnight Hand-Off

## Branches And Worktrees

- accepted clean baseline:
  - branch `main`
  - commit `dea3202`
- preserved FAST experimental line:
  - branch `fast-mode-30s`
  - checkpoint commit `367230f`
  - worktree `/tmp/overnight_fast_mode_30s`
- current Cython exact line:
  - branch `feature/cython-exact-nodechain-top3`
  - worktree `/tmp/feature_cython_exact_nodechain_top3`
  - checkpoints:
    - `4a8bcee`
    - `425c89e`
    - `87bd76d`
    - `32248fd`

## Accepted Vs Experimental On This Branch

### Safe And Useful

- evolve-only benchmark tooling in `Islam.py` and `tools/profile_islam_evolve_only.py`
- exact nodechain Cython path
- exact Roe-flux Cython path

### Experimental / Not In Exact Candidate

- update-cell Cython path
  - fast, but drifting

## Most Important Reports

- call-chain and math mapping:
  - `reports/node_iteration_call_chain.md`
  - `reports/node_iteration_math_and_state.md`
  - `reports/node_iteration_data_layout.md`
  - `reports/node_iteration_cython_plan.md`
- serial baseline and hotspot ranking:
  - `reports/serial_python_baseline.md`
  - `reports/evolve_hotspots_top3_serial.md`
- implementation notes:
  - `reports/nodechain_cython_impl.md`
  - `reports/Caculate_Roe_Flux_2_cython_impl.md`
  - `reports/Update_cell_proprity2_cython_impl.md`
- validation and speed:
  - `reports/nodechain_cython_validation.md`
  - `reports/local_kernel_profile_before_after.md`
  - `reports/cython_error_report.md`
  - `reports/cython_speed_report.md`
  - `reports/final_benchmark_matrix.md`
  - `reports/final_cython_branch_recommendation.md`

## Current Best Exact Candidate

- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_USE_CYTHON_UPDATE_CELL=0`

## Open Item

- the remaining open item is not branch viability anymore; it is only cleanup and next-step work:
  - isolate and fix the `Update_cell_proprity2` drift if this branch is to absorb the third hotspot as an accepted exact kernel
