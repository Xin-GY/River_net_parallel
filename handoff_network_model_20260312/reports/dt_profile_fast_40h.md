# dt_profile_fast_40h

- result_dir: `/tmp/overnight_fast_snapshot/handoff_network_model_20260312/result/overnight_fast_dtprofile_40h`
- total_steps: `23754`
- mean_used_dt_s: `6.0620466790835525`
- median_used_dt_s: `6.276757717132568`
- p05_used_dt_s: `5.691405773162842`
- p01_used_dt_s: `2.002155579328537`
- min_used_dt_s: `0.02880859375`
- max_used_dt_s: `6.4813737869262695`
- model_time_s: `171.44865036010742`
- model_time_per_step_s: `0.0072176749330684275`

## Limiter Category Share

| category | count |
| --- | --- |
| internal_node | 23754 |

## Schedule Reason Share

| schedule_reason | count |
| --- | --- |
| cfl_cap | 23673 |
| yield_step_cap | 79 |
| end_time_cap | 2 |

## Smallest Dt Windows

| step | time_s | used_dt_s | schedule_reason | river_name | cell_index | category | boundary_node | time_h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10595 | 64800.96875 | 0.02880859375 | cfl_cap | river8 | 15 | internal_node | n11 | 18.000269097222223 |
| 10596 | 64801.0 | 0.031689453870058 | cfl_cap | river8 | 15 | internal_node | n11 | 18.00027777777778 |
| 10597 | 64801.03515625 | 0.034858401864767 | cfl_cap | river8 | 15 | internal_node | n11 | 18.000287543402777 |
| 10598 | 64801.07421875 | 0.0383442416787147 | cfl_cap | river8 | 15 | internal_node | n11 | 18.00029839409722 |
| 10599 | 64801.1171875 | 0.0421786680817604 | cfl_cap | river8 | 15 | internal_node | n11 | 18.00031032986111 |
| 10600 | 64801.1640625 | 0.0463965348899364 | cfl_cap | river8 | 15 | internal_node | n11 | 18.000323350694444 |
| 10601 | 64801.21484375 | 0.0510361902415752 | cfl_cap | river8 | 15 | internal_node | n11 | 18.000337456597222 |
| 10602 | 64801.26953125 | 0.0561398118734359 | cfl_cap | river8 | 15 | internal_node | n11 | 18.000352647569443 |
| 10603 | 64801.33203125 | 0.0617537945508956 | cfl_cap | river8 | 15 | internal_node | n11 | 18.000370008680555 |
| 10604 | 64801.3984375 | 0.0679291784763336 | cfl_cap | river8 | 15 | internal_node | n11 | 18.00038845486111 |

## Top-K Limiter CSV

`/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/reports/dt_limiter_topk_fast_40h.csv`
