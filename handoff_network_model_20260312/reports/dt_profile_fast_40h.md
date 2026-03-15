# FAST 40h Dt Profile (speed-opt cfl3 refresh3hold)

- result_dir: `/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/result/exp_fastmode_speedopt_dtprofile_py311_40h`
- total_steps: `9836`
- mean_used_dt_s: `14.640097600650671`
- median_used_dt_s: `15.069169521331787`
- p05_used_dt_s: `13.672894716262817`
- p01_used_dt_s: `7.973964881896974`
- min_used_dt_s: `0.2`
- max_used_dt_s: `15.576638221740724`
- model_time_s: `57.58978247642517`
- model_time_per_step_s: `0.005855000251771571`

## Limiter Category Share

| category | count |
| --- | --- |
| internal_node | 9836 |

## Schedule Reason Share

| schedule_reason | count |
| --- | --- |
| cfl_cap | 9755 |
| yield_step_cap | 79 |
| end_time_cap | 2 |

## Smallest Dt Windows

| step | time_s | used_dt_s | schedule_reason | river_name | cell_index | category | boundary_node | time_h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.2 | 0.2 | cfl_cap | river1 | 15 | internal_node | n8 | 5.555555555555556e-05 |
| 6694 | 97200.0 | 0.2602272033691406 | cfl_cap | river1 | 15 | internal_node | n8 | 27.0 |
| 2 | 0.6000000000000001 | 0.4 | cfl_cap | river1 | 15 | internal_node | n8 | 0.0001666666666666667 |
| 1196 | 18000.0 | 0.4412050247192383 | cfl_cap | river1 | 15 | internal_node | n8 | 5.0 |
| 716 | 10800.0 | 0.4471158981323242 | cfl_cap | river1 | 15 | internal_node | n8 | 3.0 |
| 6695 | 97200.52045440674 | 0.5204544067382812 | cfl_cap | river1 | 15 | internal_node | n8 | 27.00014457066854 |
| 6945 | 100800.0 | 0.6776905059814453 | cfl_cap | river1 | 15 | internal_node | n8 | 28.0 |
| 3 | 1.4 | 0.8 | cfl_cap | river1 | 15 | internal_node | n8 | 0.00038888888888888887 |
| 1197 | 18000.88241004944 | 0.8824100494384766 | cfl_cap | river1 | 15 | internal_node | n8 | 5.000245113902622 |
| 717 | 10800.894231796265 | 0.8942317962646484 | cfl_cap | river1 | 15 | internal_node | n8 | 3.0002483977211845 |

## Top-K Limiter CSV

`/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/dt_limiter_topk_fast_40h.csv`
