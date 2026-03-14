# exact_dtprofile_10m_fixdt

- result_dir: `/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/result/overnight_exact_dtprofile_10m_fixdt`
- total_steps: `181`
- mean_used_dt_s: `3.314917179678685`
- median_used_dt_s: `4.843257904052734`
- p05_used_dt_s: `0.1628893762826919`
- p01_used_dt_s: `0.11465998142957683`
- min_used_dt_s: `0.1049999967217445`
- max_used_dt_s: `5.075636863708496`
- model_time_s: `2.090937852859497`
- model_time_per_step_s: `0.011552142833477884`

## Limiter Category Share

| category | count |
| --- | --- |
| internal_node | 181 |

## Schedule Reason Share

| schedule_reason | count |
| --- | --- |
| cfl_cap | 179 |
| end_time_cap | 2 |

## Smallest Dt Windows

| step | time_s | used_dt_s | schedule_reason | river_name | cell_index | category | boundary_node | time_h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.1049999967217445 | 0.1049999967217445 | cfl_cap | river1 | 15 | internal_node | n8 | 2.916666575604014e-05 |
| 2 | 0.2152499854564666 | 0.1102499887347221 | cfl_cap | river1 | 15 | internal_node | n8 | 5.979166262679628e-05 |
| 3 | 0.3310124576091766 | 0.1157624796032905 | cfl_cap | river1 | 15 | internal_node | n8 | 9.194790489143794e-05 |
| 4 | 0.4525630474090576 | 0.1215505972504615 | cfl_cap | river1 | 15 | internal_node | n8 | 0.00012571195761362712 |
| 5 | 0.5801911354064941 | 0.1276281177997589 | cfl_cap | river1 | 15 | internal_node | n8 | 0.0001611642042795817 |
| 6 | 0.7142006158828735 | 0.1340095102787017 | cfl_cap | river1 | 15 | internal_node | n8 | 0.00019838905996746487 |
| 7 | 0.8549106121063232 | 0.1407099813222885 | cfl_cap | river1 | 15 | internal_node | n8 | 0.00023747517002953425 |
| 8 | 1.002656102180481 | 0.1477454751729965 | cfl_cap | river1 | 15 | internal_node | n8 | 0.0002785155839390225 |
| 9 | 1.157788872718811 | 0.1551327407360077 | cfl_cap | river1 | 15 | internal_node | n8 | 0.0003216080201996697 |
| 10 | 1.3206782341003418 | 0.1628893762826919 | cfl_cap | river1 | 15 | internal_node | n8 | 0.0003668550650278727 |

## Top-K Limiter CSV

`/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/reports/dt_limiter_topk_exact_10m_smoke.csv`
