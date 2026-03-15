# FAST_MODE Adaptive Matrix

| label | status | wall_time_s | model_time_s | mean_nse_delta | max_abs_overall | max_peak_error | max_arrival_time_error_h | volume_error | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adaptive_10m_smoke | complete | pending | 1.44484281539917 | 0.00017983388965703284 | 0.0001823902130126953 | 0.0001823902130126953 | 0.0 | unavailable | default exact on FAST line still strict-equal to accepted exact 10m |
| adaptive_40h_default | complete | 242.30 | 235.27873492240906 | -0.00012621587765354603 | 0.03255711738423628 | 0.03255711738423628 | 0.0 | 5.60581510069191e-08 | gate was effectively always on: `29987 / 29989` steps enabled; slower and less accurate than current FAST best |
| adaptive_40h_cfl125 | complete | 193.09 | 186.73348426818848 | -0.00022049120764144892 | 0.031519703004168065 | 0.031519703004168065 | 0.0 | -4.576688050341533e-07 | best adaptive candidate so far; faster and slightly more accurate than `fast_40h_iter5_cfl125`, but still far from `30 s` and still above `1e-2` max-abs target |
| fixed_refresh2hold_cfl20 | complete | 92.689026 | 89.52261996269226 | -0.0010911349036130114 | 0.06244182586669922 | 0.024068832397460938 | 0.0 | -1.2170119024385061e-06 | first structural FAST point that clearly beats adaptive while keeping control-point `Q` error below `0.1` |
| fixed_refresh3hold_cfl20 | complete | 87.270943 | 83.9566490650177 | -0.001115237434205496 | 0.07947444915771484 | 0.017249107360839844 | 0.0 | -1.2469776837742657e-06 | current best balanced candidate: about `1.69x` wall speedup vs accepted exact with still moderate error |
| fixed_refresh3hold_cfl225 | complete | 78.14009 | 74.83811044692993 | -0.0025083002257755282 | 0.12782573699951172 | 0.017316818237304688 | 0.0 | -1.2319715822728622e-06 | faster frontier point; error rises beyond `1e-1` |
| fixed_refresh3hold_cfl30 | complete | 59.379443 | 56.126713275909424 | -0.020884883378968933 | 0.5854339599609375 | 0.01532745361328125 | 0.0 | -1.2295487328292198e-06 | current speed-optimal point; much closer to `30 s`, but `Q` error is no longer engineering-acceptable |
