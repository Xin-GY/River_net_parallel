# dt_profile_exact_40h

- result_dir: `/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/result/overnight_exact_dtprofile_40h`
- total_steps: `29969`
- mean_used_dt_s: `4.805362444425803`
- median_used_dt_s: `5.017770290374756`
- p05_used_dt_s: `4.551285457611084`
- p01_used_dt_s: `1.0512882852554322`
- min_used_dt_s: `0.0399169921875`
- max_used_dt_s: `5.184622287750244`
- model_time_s: `260.91586470603943`
- model_time_per_step_s: `0.008706191888486084`

## Limiter Category Share

| category | count |
| --- | --- |
| internal_node | 29969 |

## Schedule Reason Share

| schedule_reason | count |
| --- | --- |
| cfl_cap | 29887 |
| yield_step_cap | 80 |
| end_time_cap | 2 |

## Smallest Dt Windows

| step | time_s | used_dt_s | schedule_reason | river_name | cell_index | category | boundary_node | time_h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14546 | 70197.9921875 | 0.0399169921875 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499442274305554 |
| 14547 | 70198.03125 | 0.0419128388166427 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499453125 |
| 14548 | 70198.078125 | 0.0440084785223007 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499466145833335 |
| 14549 | 70198.125 | 0.0462088994681835 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499479166666667 |
| 14550 | 70198.171875 | 0.048519343137741 | cfl_cap | river1 | 15 | internal_node | n8 | 19.4994921875 |
| 14551 | 70198.2265625 | 0.0509453080594539 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499507378472224 |
| 14552 | 70198.28125 | 0.053492572158575 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499522569444444 |
| 14553 | 70198.3359375 | 0.0561671964824199 | cfl_cap | river1 | 15 | internal_node | n8 | 19.49953776041667 |
| 14554 | 70198.3984375 | 0.0589755550026893 | cfl_cap | river1 | 15 | internal_node | n8 | 19.499555121527777 |
| 14555 | 70198.4609375 | 0.0619243308901786 | cfl_cap | river1 | 15 | internal_node | n8 | 19.49957248263889 |

## Top-K Limiter CSV

`/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/reports/dt_limiter_topk_exact_40h.csv`
