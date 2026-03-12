# D. 优化实施

## 优化 1：跳过默认关闭的边界诊断构造

### 修改点

- 文件：`river_for_net.py`
- 位置：`_append_stage_boundary_record()`
- 修改：
  - 当 `self.enable_boundary_diagnostics == False` 时直接返回
  - 不再继续构造 `record`、不再探测界面诊断通量、也不再准备后续会被丢弃的诊断字段

### 修改原因

full-case `cProfile` 显示默认基线中以下链路占时异常高：

- `_append_stage_boundary_record` `ct=243.581 s`
- `_peek_interface_flux_for_diagnostics` `ct=198.988 s`

但默认配置下：

- `enable_diagnostics = False`
- `enable_boundary_diagnostics = False`

因此这部分工作在默认基线里没有任何对外结果产出，属于纯无效开销。

### 为什么不改变计算原理

本改动没有修改：

- PDE
- 离散格式
- 边界条件数学公式
- 汊点耦合残差
- 输出定义

它只是在“边界诊断原本就关闭”的情况下，避免构造不会被保存的诊断对象。

当 `enable_boundary_diagnostics=True` 时，原有诊断逻辑保持不变。

### 验证命令

运行：

```bash
/usr/bin/time -p -o result/exp_opt1_diagshort_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_opt1_diagshort_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  conda run -n python311 python Islam.py \
  > result/exp_opt1_diagshort_py311_40h/run.log 2>&1
```

评估：

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_opt1_diagshort_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_baseline_py311_40h \
  result/exp_opt1_diagshort_py311_40h \
  --out result/exp_opt1_diagshort_py311_40h/compare_to_baseline.json
```

### 实测收益

- 原始基线：`890.37 s`
- 优化 1：`736.00 s`
- 绝对减少：`154.37 s`
- 相对减少：`17.34%`
- 提速倍数：`1.21x`

模型内部自报时间：

- 原始基线：`832.98 s`
- 优化 1：`699.63 s`
- 绝对减少：`133.35 s`
- 相对减少：`16.01%`

### 结果校验结论

`result/eval_river11_nse.py`：

```text
node11_level =  0.873332
node11_Q     = -0.089159
node12_level =  0.911626
node12_Q     = -0.105344
mean_nse     =  0.3976138544055814
```

`tools/compare_results.py`：

- `allclose = true`
- 比较通过的关键文件：
  - `river11_raw_output.nc`
  - `river11_interpolated_output.nc`
  - `internal_node_history.csv`
  - `boundary_supercritical_counts.csv`
- 控制点：
  - `node11_level`
  - `node11_Q`
  - `node12_level`
  - `node12_Q`
  全部 `max_abs = 0.0`
- 最终时刻 `depth / level / U / Q` 全部 `max_abs = 0.0`

### 阶段结论

优化 1 可以接受：

- 有明确速度收益
- 不改变默认结果
- 不改变现有输入输出逻辑

## 结果对比脚本

### 新增文件

- `tools/compare_results.py`

### 当前功能

可比较两个结果目录中的：

- `*.nc`
- `*.csv`
- `river11` 控制点时序
- `river11` 最终时刻状态

输出指标：

- `max_abs`
- `mean_abs`
- `rmse`
- `allclose`

后续每一轮优化都复用这一个脚本做结果一致性检查。
