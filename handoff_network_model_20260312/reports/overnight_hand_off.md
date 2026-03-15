# Overnight Hand-Off

## Worktrees And Branches

- `main`
  - path: `/home/xin/River_net_parallel`
  - branch: `main`
  - role: protected exact baseline workspace
- `exact-baseline-clean`
  - path: `/tmp/overnight_exact_baseline_clean`
  - branch: `exact-baseline-clean`
  - role: clean exact line for benchmark/profiling/reporting
- `fast-mode-30s`
  - path: `/tmp/overnight_fast_mode_30s`
  - branch: `fast-mode-30s`
  - role: isolated FAST_MODE experimentation line
- `fast_mode_snapshot_20260314`
  - path: `/tmp/overnight_fast_snapshot`
  - branch: `fast_mode_snapshot_20260314`
  - role: preserved pre-cleanup FAST snapshot
- detached references
  - `/tmp/overnight_dea3202_ref`
  - `/tmp/overnight_exact_stage5_ref`

## Accepted Vs Experimental

### Accepted

- Exact safe-infrastructure/report commits on `exact-baseline-clean`:
  - `75cd416` `chore: add overnight preflight and branch layout reports`
  - `d481ee7` `chore: add benchmark harness and run summary scaffolding`
  - `e318dd1` `chore: add dt limiter profiling and 40h reports`
  - `7fbdad9` `chore: add hotpath diff report vs dea3202`
  - `698ec55` `chore: record stage-5 exact kernel experiment results`

### Experimental But Isolated

- FAST adaptive gating on `fast-mode-30s`
  - modifies:
    - `Islam.py`
    - `Rivernet.py`
    - `river_for_net.py`
    - `tools/evaluate_fast_mode.py`
  - current best result:
    - `result/exp_fastmode_adaptive_cfl125_py311_40h`
  - status:
    - candidate for a FAST-only accepted commit
    - not acceptable for default exact path

### Rejected / Not Merged Into Default Exact

- exact fused orchestration extensions beyond the current accepted baseline
- exact local-kernel experiment preserved as:
  - `reports/stage5_failed_local_kernel_experiment.diff`

## Key Report Paths

- stage log:
  - `reports/overnight_progress_log.md`
- benchmark matrix:
  - `reports/benchmark_matrix.md`
- exact dt profile:
  - `reports/dt_profile_exact_40h.md`
- fast dt profile:
  - `reports/dt_profile_fast_40h.md`
- hotpath diff vs `dea3202`:
  - `reports/hotpath_diff_vs_dea3202.md`
- exact local-kernel before/after:
  - `reports/local_kernel_profile_before_after.md`
- final recommendation:
  - `reports/final_overnight_recommendation.md`
- FAST adaptive design:
  - `/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fastmode_adaptive_design.md`
- FAST adaptive matrix:
  - `/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fastmode_adaptive_matrix.md`
- FAST error report vs accepted exact baseline:
  - `/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_eval_vs_accepted40h.md`

## Current Best Results

### Exact

- accepted exact baseline reference:
  - wall: `147.10 s`
  - model/evolve: `139.86 s`
- clean exact rerun on the overnight line:
  - wall: `262.34158 s`
  - model/evolve: `254.96488738059998 s`
  - strict compare: passed
- conclusion:
  - no new exact performance commit is acceptable from this overnight run

### FAST

- previous FAST best:
  - `fast_40h_iter5_cfl125`
  - wall: `195.54 s`
  - model/evolve: `192.66340517997742 s`
  - max abs overall: `0.031598621848008435`
- new FAST adaptive best:
  - `fast_40h_adaptive_cfl125`
  - wall: `193.09 s`
  - model/evolve: `186.73348426818848 s`
  - max abs overall: `0.031519703004168065`
- conclusion:
  - a modest FAST-only improvement exists
  - the path remains experimental and isolated from default exact

## Most Recommended Next Step

If the next round stays exact, go after larger river-body kernels in Cython and keep strict compare gates in place.

If the next round is allowed to stay approximate, keep FAST isolated and move up one architectural level:

1. local time stepping / multi-rate stepping
2. semi-implicit internal-node coupling
3. larger compiled kernels for river-body loops
