# Overnight Hand-Off

## Worktrees And Branches

- main workspace:
  - `/home/xin/River_net_parallel`
  - branch `main`
  - kept as the accepted exact baseline side
- FAST workspace:
  - `/tmp/overnight_fast_mode_30s`
  - branch `fast-mode-30s`
  - this is where the overnight FAST experiments were run
- FAST safety checkpoint:
  - `/tmp/fast_mode_safety_20260315_194332`
  - branch `safety_fast_20260315_194332`
- exact clean reference:
  - `/tmp/overnight_exact_baseline_clean`
  - branch `exact-baseline-clean`

## What Is Accepted vs Experimental

### Safe To Keep

- FAST-only periodic internal-node refresh controls:
  - `ISLAM_FAST_NODE_REFRESH_EVERY`
  - `ISLAM_FAST_NODE_REFRESH_MODE`
  - `ISLAM_FAST_NODE_REFRESH_WARMUP_STEPS`
- sweep / evaluation / dt-profile infrastructure:
  - [fast_sweep.py](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/tools/fast_sweep.py)
  - [evaluate_fast_mode.py](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/tools/evaluate_fast_mode.py)
  - [dt_profile_report.py](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/tools/dt_profile_report.py)
- default exact smoke remains runnable on the FAST line

### Experimental FAST Results

- best balanced:
  - `response_root_iter2_cfl20_dt135_fixed_refresh3hold`
  - result dir: [sweep_response_root_iter2_cfl20_dt135_fixed_refresh3hold](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/result/sweep_response_root_iter2_cfl20_dt135_fixed_refresh3hold)
- fastest:
  - `response_root_iter2_cfl30_dt20_fixed_refresh3hold`
  - result dir: [sweep_response_root_iter2_cfl30_dt20_fixed_refresh3hold](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/result/sweep_response_root_iter2_cfl30_dt20_fixed_refresh3hold)

## Key Report Paths

- FAST sweep matrix:
  - [fast_sweep_matrix.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_sweep_matrix.md)
- FAST Pareto / top candidates:
  - [fast_sweep_top_candidates.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_sweep_top_candidates.md)
- best balanced error report:
  - [fast_eval_vs_accepted40h.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_eval_vs_accepted40h.md)
- fastest error report:
  - [fast_eval_speed_opt_vs_accepted40h.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_eval_speed_opt_vs_accepted40h.md)
- speed-optimal dt profile:
  - [dt_profile_fast_40h.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/dt_profile_fast_40h.md)
  - [dt_limiter_topk_fast_40h.csv](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/dt_limiter_topk_fast_40h.csv)
- final recommendation:
  - [final_fastmode_recommendation.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/final_fastmode_recommendation.md)
- progress log:
  - [overnight_progress_log.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/overnight_progress_log.md)

## Current Recommendation

If the next person wants the best engineering balance, start from:

- `response_root_iter2_cfl20_dt135_fixed_refresh3hold`

If the next person wants the fastest currently demonstrated wall-clock, start from:

- `response_root_iter2_cfl30_dt20_fixed_refresh3hold`

## Most Recommended Next Direction

Do not go back to exact-only cleanup or fast-path admission work.

The most promising next iteration is:

1. hotspot-only node refresh / asynchronous coupling
2. multi-rate stepping around the internal-node limiter hot spots
3. then FAST-only local river kernel cost reduction
