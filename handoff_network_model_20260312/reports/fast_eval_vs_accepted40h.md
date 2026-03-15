# FAST_MODE Evaluation

- baseline: /home/xin/River_net_parallel/handoff_network_model_20260312/result/exp_optghr_process_auto_py311_40h
- candidate: /tmp/overnight_fast_mode_30s/handoff_network_model_20260312/result/sweep_response_root_iter2_cfl20_dt135_fixed_refresh3hold

## Speed
- baseline wall: {'real': 147.1}
- candidate wall: {'real': 87.270943}
- baseline model time: 139.86
- candidate model time: 83.9566490650177
- wall speedup: 1.685555294160165
- model speedup: 1.665859721148347

## NSE
- baseline mean NSE: 0.449093
- candidate mean NSE: 0.447978
- mean NSE delta: -0.001115

## Control Point Error
- node11_level: max_abs=0.00339355, rmse=0.000958683, peak_err=-0.000869147, peak_dt_h=0
- node11_Q: max_abs=0.0794744, rmse=0.0111742, peak_err=0.00994396, peak_dt_h=0
- node12_level: max_abs=0.002232, rmse=0.000885664, peak_err=-0.000837591, peak_dt_h=0
- node12_Q: max_abs=0.027735, rmse=0.00892284, peak_err=0.0172491, peak_dt_h=0

## Volume
- baseline network relative volume change: 0.000220894
- candidate network relative volume change: 0.000219647
- network relative volume delta: -1.24698e-06
- max river relative volume delta: 4.39832e-05

## Internal Node History
- unavailable: missing_file
