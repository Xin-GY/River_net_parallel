# Runbook

## 环境

推荐环境：
- `conda` 环境名：`python311`

需要的第三方库至少包括：
- `numpy`
- `pandas`
- `scipy`
- `xarray`
- `matplotlib`
- `networkx`
- `shapely`
- `pyproj`

可选编译优化：
- `Cython`

## 构建可选 Cython 断面表后端

只在需要启用当前最快 CPU 路径时执行：

```bash
conda run -n python311 python -m pip install Cython
conda run -n python311 python build_cython_cross_section.py build_ext --inplace
```

说明：
- 运行时会优先尝试导入 `cython_cross_section`。
- 只有在设置 `ISLAM_USE_CYTHON_TABLE=1` 且扩展已成功构建时，才会启用编译后的断面表查表逻辑。
- 若扩展不存在，代码会自动回退到原始 Python 版本。

## 运行 Islam 40h 当前 handoff 基线

在本目录下执行：

```bash
mkdir -p /tmp/mplconfig
MPLCONFIGDIR=/tmp/mplconfig ISLAM_OUTPUT_PATH=result/exp_handoff_run ISLAM_SIM_END_TIME='2024-01-02 16:00:00' ISLAM_OUTPUT_RIVERS=river11 ISLAM_USE_FINE_INTERPOLATION=0 conda run -n python311 python Islam.py
```

说明：
- 当前 handoff 最新结果使用的是 `ISLAM_USE_FINE_INTERPOLATION=0`
- 如果要复现 Fine 版本，把该环境变量改成 `1`

## 运行当前最快且结果一致的 CPU 路径

```bash
mkdir -p /tmp/mplconfig
MPLCONFIGDIR=/tmp/mplconfig \
ISLAM_OUTPUT_PATH=result/exp_parallel_process_cython_chi_py311_40h \
ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
ISLAM_OUTPUT_RIVERS=river11 \
ISLAM_USE_FINE_INTERPOLATION=0 \
ISLAM_USE_PARALLEL=1 \
ISLAM_PARALLEL_BACKEND=process \
ISLAM_N_WORKERS=4 \
ISLAM_SAVE_CFL_HISTORY=1 \
ISLAM_USE_CYTHON_TABLE=1 \
conda run -n python311 python Islam.py
```

说明：
- 该路径对应当前已验证的最快 full-case 严格校验通过 baseline。
- 若要关闭并行，设置 `ISLAM_USE_PARALLEL=0`。
- 若要关闭 Cython 断面表后端，设置 `ISLAM_USE_CYTHON_TABLE=0`。

## 评估 NSE

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_handoff_run
```

## 打包图和绘图数据

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/package_river11_report.py result/exp_handoff_run
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
