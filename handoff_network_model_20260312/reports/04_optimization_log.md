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

## 优化 2：缓存固定拓扑下的河道 edge 列表与 bound method

### 修改点

- 文件：`Rivernet.py`
- 新增：
  - `_refresh_river_cache()`
  - `self._river_edges`
  - `self._river_method_cache`
- 修改：
  - `call_river_function_by_name()` 改为按函数名缓存已绑定 method
  - 多个高频 wrapper 改为遍历 `self._river_edges`，不再每次重新走 `self.G.edges(data=True)`

### 修改原因

full-case `cProfile` 表明：

- `call_river_function_by_name` 被调用 `179815` 次
- `networkx/classes/reportviews.py` 聚合纯耗时约 `42.312 s`

河网拓扑在当前 workflow 中是固定的，因此：

- 重复生成 edge view
- 重复做 `hasattr/getattr/callable`

都属于可压缩的纯 Python 调度成本。

### 为什么不改变计算原理

本改动不改变：

- 河道求解器
- 内部节点耦合公式
- 外边界条件
- 输出逻辑

它只把“固定拓扑下的对象分派方式”从反复动态查找，改成初始化后缓存。

### 验证命令

运行：

```bash
/usr/bin/time -p -o result/exp_opt2_rivercache_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_opt2_rivercache_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  conda run -n python311 python Islam.py \
  > result/exp_opt2_rivercache_py311_40h/run.log 2>&1
```

比较：

```bash
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_opt2_rivercache_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_baseline_py311_40h \
  result/exp_opt2_rivercache_py311_40h \
  --out result/exp_opt2_rivercache_py311_40h/compare_to_baseline.json
conda run -n python311 python tools/compare_results.py \
  result/exp_opt1_diagshort_py311_40h \
  result/exp_opt2_rivercache_py311_40h \
  --out result/exp_opt2_rivercache_py311_40h/compare_to_opt1.json
```

### 实测收益

- 优化 1：`736.00 s`
- 优化 2：`731.92 s`
- 相对优化 1：
  - 绝对减少：`4.08 s`
  - 相对减少：`0.55%`
  - 提速倍数：`1.01x`
- 相对原始基线：
  - 绝对减少：`158.45 s`
  - 相对减少：`17.80%`
  - 提速倍数：`1.22x`

模型内部自报时间：

- 优化 1：`699.63 s`
- 优化 2：`695.04 s`
- 相对优化 1 进一步减少：`4.59 s`

### 结果校验结论

- 四个 NSE 与基线完全一致
- `tools/compare_results.py` 对：
  - `exp_baseline_py311_40h` vs `exp_opt2_rivercache_py311_40h`
  - `exp_opt1_diagshort_py311_40h` vs `exp_opt2_rivercache_py311_40h`
  均返回 `allclose = true`

### 阶段结论

优化 2 可以保留，但它属于“小收益、低风险”类型：

- 正确性完全通过
- 有正向收益
- 但收益幅度很小

后续更值得投入的是：

- 内部节点高频函数里的 `in_edges/out_edges` 邻接缓存

## 优化 3：缓存节点入边/出边邻接，压缩内部节点耦合调度开销

### 修改点

- 文件：`Rivernet.py`
- 在 `_refresh_river_cache()` 中新增：
  - `self._in_edges_by_node`
  - `self._out_edges_by_node`
- 修改：
  - `classfy_nodes()` 基于缓存邻接判定 `internal / external_in / external_out`
  - 内部节点相关高频函数改为直接读取缓存邻接，不再重复调用 `self.G.in_edges()` / `self.G.out_edges()`
  - 包括节点水位平均、特征量 `Ac` 计算、结点目标水位施加、净流量统计、内部节点历史写出等路径

### 修改原因

full-case `cProfile` 已经表明内部节点更新链是主热点：

- `Update_internal_boundary_conditions` `ct=904.543 s`
- `_apply_internal_node_levels` `ct=848.134 s`
- `Apply_node_target_level_V4` `ct=847.054 s`

这些函数内部大量重复访问：

- `self.G.in_edges(node, data=True)`
- `self.G.out_edges(node, data=True)`

当前案例拓扑在模拟开始后保持不变，因此每步、每节点重新构造 networkx 邻接 view 属于纯 Python 调度开销。

### 为什么不改变计算原理

本改动没有改变：

- 河道内部推进
- 结点耦合公式
- 边界条件定义
- 输出字段与输出频率

它只把“固定拓扑下的节点邻接访问方式”从重复查询 networkx view，改为初始化后缓存的同一组边对象。

### 验证命令

运行：

```bash
/usr/bin/time -p -o result/exp_opt3_nodecache_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_opt3_nodecache_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  conda run -n python311 python Islam.py \
  > result/exp_opt3_nodecache_py311_40h/run.log 2>&1
```

评估：

```bash
cd handoff_network_model_20260312
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_opt3_nodecache_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_baseline_py311_40h \
  result/exp_opt3_nodecache_py311_40h \
  --out result/exp_opt3_nodecache_py311_40h/compare_to_baseline.json
conda run -n python311 python tools/compare_results.py \
  result/exp_opt2_rivercache_py311_40h \
  result/exp_opt3_nodecache_py311_40h \
  --out result/exp_opt3_nodecache_py311_40h/compare_to_opt2.json
```

### 实测收益

- 优化 2：`731.92 s`
- 优化 3：`698.01 s`
- 相对优化 2：
  - 绝对减少：`33.91 s`
  - 相对减少：`4.63%`
  - 提速倍数：`1.05x`
- 相对原始基线：
  - 绝对减少：`192.36 s`
  - 相对减少：`21.60%`
  - 提速倍数：`1.28x`

模型内部自报时间：

- 优化 2：`695.04 s`
- 优化 3：`660.93 s`
- 相对优化 2 进一步减少：`34.11 s`

### 结果校验结论

- 四个 NSE 与基线完全一致
- `tools/compare_results.py` 对：
  - `exp_baseline_py311_40h` vs `exp_opt3_nodecache_py311_40h`
  - `exp_opt2_rivercache_py311_40h` vs `exp_opt3_nodecache_py311_40h`
  均返回 `allclose = true`
- 关键时序、内部节点历史、`river11_raw_output.nc`、`river11_interpolated_output.nc` 全部逐点一致

### 阶段结论

优化 3 可以接受：

- 收益明显大于优化 2
- 不改变现有功能和输入输出
- 结果与基线逐点一致
