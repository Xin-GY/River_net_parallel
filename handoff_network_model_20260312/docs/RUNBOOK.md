# Runbook

## 环境

推荐环境：
- `conda` 环境名：`python310`

需要的第三方库至少包括：
- `numpy`
- `pandas`
- `scipy`
- `xarray`
- `matplotlib`
- `networkx`
- `shapely`
- `pyproj`

## 运行 Islam 40h 当前 handoff 基线

在本目录下执行：

```bash
mkdir -p /tmp/mplconfig
MPLCONFIGDIR=/tmp/mplconfig ISLAM_OUTPUT_PATH=result/exp_handoff_run ISLAM_SIM_END_TIME='2024-01-02 16:00:00' ISLAM_OUTPUT_RIVERS=river11 ISLAM_USE_FINE_INTERPOLATION=0 conda run -n python310 python Islam.py
```

说明：
- 当前 handoff 最新结果使用的是 `ISLAM_USE_FINE_INTERPOLATION=0`
- 如果要复现 Fine 版本，把该环境变量改成 `1`

## 评估 NSE

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python310 python result/eval_river11_nse.py result/exp_handoff_run
```

## 打包图和绘图数据

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python310 python result/package_river11_report.py result/exp_handoff_run
```

输出目录：
- `result/report_packages/exp_handoff_run/`

## 重点看哪些文件

- 四张图：
  - `node11_level_compare.png`
  - `node11_Q_compare.png`
  - `node12_level_compare.png`
  - `node12_Q_compare.png`
- 指标：
  - `nse_summary.csv`
- 节点诊断：
  - `internal_node_history.csv`
- 外边界超临界触发统计：
  - `boundary_supercritical_counts.csv`
