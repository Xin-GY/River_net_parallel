# B. 基准建立

## 1. 基准运行目标

严格按当前 handoff 的原始串行逻辑，在 CPU 上复跑 40h Islam 基线，不做任何代码优化或 profile 插桩。

额外约束：

- 使用用户指定的 `conda` `python311` 环境。
- 保留当前 handoff 的输入输出逻辑。
- 保持与 docs 中 baseline 相同的案例配置：
  - `ISLAM_SIM_END_TIME='2024-01-02 16:00:00'`
  - `ISLAM_OUTPUT_RIVERS=river11`
  - `ISLAM_USE_FINE_INTERPOLATION=0`

## 2. 环境信息

- Python: `3.11.11`
- CPU logical cores: `20`
- Platform: `Linux-5.15.146.1-microsoft-standard-WSL2-x86_64-with-glibc2.35`
- Machine: `x86_64`

已验证 `python311` 环境内存在以下依赖：

- `numpy`
- `pandas`
- `scipy`
- `xarray`
- `matplotlib`
- `networkx`
- `shapely`
- `pyproj`
- `h5netcdf`

## 3. 运行命令

在目录 `handoff_network_model_20260312/` 下执行：

```bash
mkdir -p /tmp/mplconfig
/usr/bin/time -p -o result/exp_baseline_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_baseline_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  conda run -n python311 python Islam.py \
  > result/exp_baseline_py311_40h/run.log 2>&1
```

后处理命令：

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_baseline_py311_40h
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/package_river11_report.py result/exp_baseline_py311_40h
```

## 4. 基准结果路径

### 原始运行结果

- `result/exp_baseline_py311_40h/`

包含：

- `river11_raw_output.nc`
- `river11_interpolated_output.nc`
- `internal_node_history.csv`
- `boundary_supercritical_counts.csv`
- `net.png`
- `run.log`
- `time.txt`

### 打包后评估结果

- `result/report_packages/exp_baseline_py311_40h/`

包含：

- `nse_summary.csv`
- `node*_sim_raw.csv`
- `node*_real.csv`
- `node*_compare_on_real_time.csv`
- `*_compare.png`
- `river11_four_curves_compare.png`
- `report_meta.json`
- `river11_interpolated_output.nc`

## 5. 原始耗时

`time.txt` 记录：

```text
real 890.37
user 871.38
sys 3.68
```

结论：

- 原始串行 40h 基线墙钟耗时约 `890.37 s`
- 约等于 `14 分 50 秒`

运行日志末尾还给出模型内部自报时间：

- `共计算 29969 步`
- `总耗时: 832.98 秒`

说明：

- `/usr/bin/time` 的外部 wall time 比模型内部自报时间高约 `57.39 s`
- 这部分主要包含 `conda run` 启动开销、Python 进程收尾、字体缓存等运行壳层成本

## 6. 基准评估结果

`result/eval_river11_nse.py` 输出：

```text
      series       nse
node11_level  0.873332
    node11_Q -0.089159
node12_level  0.911626
    node12_Q -0.105344
mean_nse= 0.3976138544055814
flow_direction_mode= auto_dominant_positive
applied_flow_sign= 1
```

`result/package_river11_report.py` 输出的 Bias/RMSE：

```text
      series       nse     bias     rmse
node11_level  0.873332 0.055906 0.060641
    node11_Q -0.089159 0.581798 1.470787
node12_level  0.911626 0.034364 0.050672
    node12_Q -0.105344 0.605420 1.495783
mean_nse= 0.3976138544055814
```

## 7. 与 handoff 内置基准的一致性

参考基准目录：

- `artifacts/latest_handoff/`
- `artifacts/historical_best/`

两者在当前 handoff 包中逐文件完全一致。

本次 `python311` 基线与 `artifacts/latest_handoff/` 的对比结论：

- 四个 NSE 数值完全一致。
- `node11_Q_sim_raw.csv` 与 `node12_Q_sim_raw.csv` 字节级一致。
- 其余 level 和 compare CSV 虽然文件字节不完全一致，但数值差异仅在浮点舍入误差量级。

已量化的最大误差：

- `node11_level_sim_raw.csv`
  - `sim_value max abs diff = 8.882e-16`
- `node12_level_sim_raw.csv`
  - `sim_value max abs diff = 4.441e-16`
- `node11_level_compare_on_real_time.csv`
  - `sim_interp_on_real_time max abs diff = 8.882e-16`
  - `residual max abs diff = 9.021e-16`
- `node11_Q_compare_on_real_time.csv`
  - `sim_interp_on_real_time max abs diff = 3.553e-15`
- `node12_level_compare_on_real_time.csv`
  - `sim_interp_on_real_time max abs diff = 4.441e-16`
- `node12_Q_compare_on_real_time.csv`
  - 全列数值一致

因此本次 `python311` 原始串行基线可视为与 handoff 内置基准一致。

## 8. 阶段结论

### 已确认事实

1. `python311` 环境可直接运行当前 handoff。
2. 当前 handoff 原始串行 40h 基线耗时约 `14 分 50 秒`。
3. 当前结果与 handoff 内置基准一致，偏差仅为机器精度量级。
4. 当前距离“1 分钟以内”目标约差 `14.8x`。

### 对后续优化的约束含义

- 后续所有优化必须以本次 `exp_baseline_py311_40h` 作为速度与结果一致性的对照基准。
- 任何优化后结果，至少要复核：
  - `river11_interpolated_output.nc`
  - 四条目标时序
  - `nse_summary.csv`
  - 关键 CSV 的误差统计

本阶段未做任何求解逻辑修改。
