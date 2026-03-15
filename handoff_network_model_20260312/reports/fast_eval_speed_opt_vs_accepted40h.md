# FAST_MODE Evaluation

- baseline: /home/xin/River_net_parallel/handoff_network_model_20260312/result/exp_optghr_process_auto_py311_40h
- candidate: /tmp/overnight_fast_mode_30s/handoff_network_model_20260312/result/sweep_response_root_iter2_cfl30_dt20_fixed_refresh3hold

## Speed
- baseline wall: {'real': 147.1}
- candidate wall: {'real': 59.379443}
- baseline model time: 139.86
- candidate model time: 56.126713275909424
- wall speedup: 2.4772883100301226
- model speedup: 2.491861572447186

## NSE
- baseline mean NSE: 0.449093
- candidate mean NSE: 0.428208
- mean NSE delta: -0.020885

## Control Point Error
- node11_level: max_abs=0.00611362, rmse=0.0010859, peak_err=-0.000781219, peak_dt_h=0
- node11_Q: max_abs=0.585434, rmse=0.0598818, peak_err=0.00933361, peak_dt_h=0
- node12_level: max_abs=0.00746173, rmse=0.00107207, peak_err=-0.000745466, peak_dt_h=0
- node12_Q: max_abs=0.450917, rmse=0.0604276, peak_err=0.0153275, peak_dt_h=0

## Volume
- baseline network relative volume change: 0.000220894
- candidate network relative volume change: 0.000219665
- network relative volume delta: -1.22955e-06
- max river relative volume delta: 4.33775e-05

## Internal Node History
- unavailable: missing_file
