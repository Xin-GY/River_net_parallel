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

## 优化 4：缓存内部节点分支 `(river, name)` 对，压缩热点循环中的 payload 解包

### 修改点

- 文件：`Rivernet.py`
- 在 `_refresh_river_cache()` 中新增：
  - `self._in_branches_by_node`
  - `self._out_branches_by_node`
- 修改：
  - 内部节点与外部边界的高频循环不再反复解包 `(_, _, data)` 再做 `data['river'] / data['name']`
  - 改为直接遍历预缓存的 `(river, name)` 二元组
  - 涉及：
    - `Update_external_boundary_conditions_V2`
    - `Caculate_node_average_level_at_real_cell`
    - `Caculate_node_Ac_at_ghost_cell*`
    - `Caculate_node_average_level_at_ghost_cell`
    - `Apply_node_target_level*`
    - `Get_node_clear_flow_*`
    - `internal_node_history` 写出路径

### 修改原因

优化 3 之后，内部节点链路仍然是当前最重的纯 Python 调度热点。虽然邻接 view 已经缓存，但热点循环里仍然存在大量：

- tuple 解包
- `data['river']`
- `data.get('name', 'river')`

这些访问不改变数学逻辑，但在 `Apply_node_target_level_V4`、`Get_node_clear_flow_*`、内部节点历史写出等高频路径中会持续累积。

### 为什么不改变计算原理

本改动没有改变：

- 任意一条河道的求解过程
- 任意内部节点的耦合方程
- 边界条件数值公式
- 输出字段、输出频率、输出内容定义

它只是把固定拓扑下的 branch payload 访问，从“每次循环查 `data` 字典”改成“初始化后直接取缓存好的 `(river, name)` 元组”。

### 验证命令

运行：

```bash
/usr/bin/time -p -o result/exp_opt6_branchcache_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_opt6_branchcache_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  conda run -n python311 python Islam.py \
  > result/exp_opt6_branchcache_py311_40h/run.log 2>&1
```

评估：

```bash
cd handoff_network_model_20260312
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_opt6_branchcache_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_baseline_py311_40h \
  result/exp_opt6_branchcache_py311_40h \
  --out result/exp_opt6_branchcache_py311_40h/compare_to_baseline.json
```

### 实测收益

- 优化 3：`698.01 s`
- 优化 4：`689.86 s`
- 相对优化 3：
  - 绝对减少：`8.15 s`
  - 相对减少：`1.17%`
  - 提速倍数：`1.01x`
- 相对原始基线：
  - 绝对减少：`200.51 s`
  - 相对减少：`22.52%`
  - 提速倍数：`1.29x`

模型内部自报时间：

- 优化 3：`660.93 s`
- 优化 4：`653.71 s`
- 相对优化 3 进一步减少：`7.22 s`

### 结果校验结论

- 四个 NSE 与基线完全一致
- `tools/compare_results.py` 返回 `allclose = true`
- `internal_node_history.csv`、`river11_raw_output.nc`、`river11_interpolated_output.nc`、控制点时序、最终状态全部 `max_abs = 0.0`

### 阶段结论

优化 4 可以接受：

- 收益不算大，但是真正是“净收益”
- 不引入任何浮点差异
- 继续把内部节点链路的纯 Python 调度成本向下压缩

## 未合入试验

以下试验已完整跑通并校验，但未满足“当前最优且结果完全一致”的要求，因此不合入：

- `river_for_net.py` 断面表对象缓存：
  - 结果逐点一致
  - wall time `703.80 s`
  - 比优化 3 更慢，已回退
- `river_for_net.py` numba 标量插值：
  - wall time `681.66 s`
  - 主输出与最终状态一致，但 `internal_node_history.csv` 中若干 `face_Q` 列出现 `1e-13` 量级差异
  - 不满足“所有现有输出逐点一致”，已回退
- `river_for_net.py` numba 标量插值（保留 `width` 走原始 `np.interp`）：
  - wall time `709.54 s`
  - 仍存在 `internal_node_history.csv` 微小差异，且速度更差
  - 已回退
- 持久化线程池（河道局部阶段并行）：
  - 初版 wall time `20.43 s / 10min`
  - 原因：GIL 与线程调度开销明显高于收益
  - 修正 `dt` 精度链后可做到结果逐点一致，但仍显著慢于串行 `8.94 s / 10min`
  - 不作为最终方案

## 优化 5：持久化进程池并修正并行分支的 dt 精度链

### 修改点

- 文件：`parallel_river_pool.py`
- 新增：
  - `PersistentRiverThreadPool`
  - `PersistentRiverProcessPool`
  - 基于 `Pipe` 的常驻 worker 机制
  - worker 侧河道状态驻留
  - `interface_snapshots / get_rivers / call_batch` 三类命令
- 文件：`Rivernet.py`
  - 新增 `parallel_backend`
  - 线程后端保留作 exact 对照
  - 进程后端复用现有 junction snapshot 两阶段链路
  - Linux 下进程后端默认将 `spawn` 回退为 `fork`
  - 新增可选 `cfl_history.csv` 诊断输出
- 文件：`Islam.py`
  - 新增环境变量：
    - `ISLAM_PARALLEL_BACKEND`
    - `ISLAM_SAVE_CFL_HISTORY`

### 修改原因

在尝试多线程/多进程后，发现并行版与串行版最早的分叉出现在 `dt` 序列：

- `internal_node_history.csv` 的 `time` 从第 3 步开始出现 `1e-8 s` 量级差异
- `cfl_history.csv` 诊断显示：并不是某条河道先偏，而是同一步所有河道的 CFL 候选 `dt` 一起偏

根因是并行分支中：

- `self.cfl_allowed_dt = min(float(v) for v in dt_map.values())`

把串行路径里的 `np.float32` 风格 `DT` 链强制提升成了 Python `float64`。在当前求解器中，前期时间步主要受：

- `DT_old * DT_increase_factor`

约束，因此这处精度提升会让整个全局 `dt` 序列从第 3 步开始统一走向另一条浮点链，最终累积出可见状态差异。

修正方式是：

- 并行分支不再 `float()` 化每条河道返回的 `dt`
- 保持与串行路径一致的标量精度链

修正后：

- 线程版与串行版重新达到逐点一致
- 进程版也达到逐点一致，并在 40h 全案例上取得真实正收益

### 为什么不改变计算原理

本改动没有改变：

- 控制方程
- 离散格式
- 边界条件公式
- 结点耦合数学含义
- 输出定义

进程版只是把“河道局部阶段”放入常驻 worker 执行，河网连接点仍按既有两阶段逻辑交换必要接口量；而 `dt` 修正仅仅是让并行分支回到与串行完全一致的数值精度链。

### 验证命令

10 分钟 exact smoke：

```bash
/usr/bin/time -p -o result/exp_parallel_process_fixdt_py311_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_fixdt_py311_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_SAVE_CFL_HISTORY=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_fixdt_py311_40h_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_fixdt_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  conda run -n python311 python Islam.py
```

对比：

```bash
cd handoff_network_model_20260312
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_parallel_process_fixdt_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_opt6_branchcache_py311_40h \
  result/exp_parallel_process_fixdt_py311_40h \
  --out result/exp_parallel_process_fixdt_py311_40h/compare_to_opt6.json
```

### worker 数量摸底

10 分钟 smoke：

- 串行：`8.94 s`
- 进程 `2 workers`：`7.96 s`
- 进程 `4 workers`：`6.89 s`
- 进程 `8 workers`：`7.21 s`

因此当前机器上先采用 `4 workers`。

### 实测收益

40 小时 full-case：

- 当前最佳串行：`689.86 s`
- 优化 5（进程，4 workers）：`659.30 s`
- 相对优化 4：
  - 绝对减少：`30.56 s`
  - 相对减少：`4.43%`
  - 提速倍数：`1.05x`
- 相对原始基线：
  - 绝对减少：`231.07 s`
  - 相对减少：`25.95%`
  - 提速倍数：`1.35x`

模型内部自报时间：

- 当前最佳串行：`653.71 s`
- 优化 5：`616.51 s`
- 相对优化 4 进一步减少：`37.20 s`

### 结果校验结论

- `result/eval_river11_nse.py` 四个 NSE 与串行完全一致
- `tools/compare_results.py` 返回 `allclose = true`
- `internal_node_history.csv`
- `river11_raw_output.nc`
- `river11_interpolated_output.nc`
- `boundary_supercritical_counts.csv`
- 控制点时序
- 最终状态

全部 `max_abs = 0.0`

### 阶段结论

优化 5 可以接受：

- 是当前第一条“多进程且完全一致”的路径
- 收益虽然离 1 分钟目标仍很远，但是真正超过了当前最佳串行
- 进程后端值得保留为后续继续提速的基础设施

## 优化 6：合并进程边界往返并压缩接口 snapshot 结构

### 修改点

- 文件：`parallel_river_pool.py`
  - 新增 `call_batch_and_interface_snapshots`
  - worker 新增同名命令：在一次往返内先执行本批边界操作，再直接回传该 worker 的接口 snapshot
  - 接口 snapshot 由多层字典改为定长紧凑元组
  - 删除并行路径中未被消费的冗余 snapshot 字段
- 文件：`Rivernet.py`
  - `_update_boundary_conditions_parallel()` 改为统一使用 `call_batch_and_interface_snapshots`
  - 并行结点残差、Ac、历史写出改为读取紧凑 snapshot

### 修改原因

优化 5 的 10 分钟 process `cProfile` 显示：

- `_collect` 调用 `25790` 次
- `multiprocessing.connection.recv` 累计 `5.475 s`
- `_update_boundary_conditions_parallel` 累计 `3.842 s`

这说明进程版当前最大的可压缩开销不是河道核本身，而是：

- 每次内部结点迭代都要经历
  - 一次 `call_batch`
  - 一次 `get_interface_snapshots`
- 并且 snapshot 使用了层级较深、对象数量较多的字典结构

因此这一轮只做两件事：

- 把“apply 内部/外部边界 + 取 snapshot”合并成一次 worker 往返
- 在不改变字段数值的前提下，把 snapshot 结构压成紧凑定长结构，减少 pickle / 解包开销

### 为什么不改变计算原理

本改动没有改变：

- 单河道求解器
- 边界条件公式
- 结点牛顿/JPWSPC 迭代公式
- CFL 控制
- 输出定义

它只改变了进程后端中：

- worker 和主进程之间的握手协议
- snapshot 的内部表示形式

也就是说，仍然是原来的边界操作、原来的迭代顺序、原来的结果写出，只是减少了 IPC 次数和对象构造数量。

### 验证命令

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_proc_batchsnap_tuple_10m_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_proc_batchsnap_tuple_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_SAVE_CFL_HISTORY=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_tuple_py311_40h_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_tuple_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_SAVE_CFL_HISTORY=1 \
  conda run -n python311 python Islam.py
```

结果对比：

```bash
cd handoff_network_model_20260312
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_parallel_process_tuple_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_opt6_branchcache_py311_40h \
  result/exp_parallel_process_tuple_py311_40h \
  --out result/exp_parallel_process_tuple_py311_40h/compare_to_best_serial.json
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_fixdt_py311_40h \
  result/exp_parallel_process_tuple_py311_40h \
  --out result/exp_parallel_process_tuple_py311_40h/compare_to_prev_process.json
```

### 过程观察

10 分钟 process `cProfile` 在“融合往返”后显示：

- `_collect`：`25790 -> 15886`
- `recv`：`25790 -> 15886`
- `_update_boundary_conditions_parallel`：`3.842 s -> 3.457 s`

说明主方向判断是对的：结点耦合阶段确实因为往返次数下降而变轻。

紧凑 tuple snapshot 在 `cProfile` 下并没有稳定给出更好数字，但真实 wall time 持续下降，因此最终是否接受仍以：

- 无 profile 的真实 wall time
- 全量结果一致性

为准。

### 实测收益

10 分钟 smoke：

- 优化 5：`6.89 s`
- 优化 6：`6.53 s`
- 绝对减少：`0.36 s`
- 相对减少：`5.22%`

40 小时 full-case：

- 优化 5（进程，4 workers）：`659.30 s`
- 优化 6（进程，4 workers）：`612.93 s`
- 相对优化 5：
  - 绝对减少：`46.37 s`
  - 相对减少：`7.03%`
  - 提速倍数：`1.08x`
- 相对当前最佳串行：
  - 绝对减少：`76.93 s`
  - 相对减少：`11.15%`
  - 提速倍数：`1.13x`
- 相对原始基线：
  - 绝对减少：`277.44 s`
  - 相对减少：`31.16%`
  - 提速倍数：`1.45x`

模型内部自报时间：

- 优化 5：`616.51 s`
- 优化 6：`569.99 s`
- 相对优化 5 进一步减少：`46.52 s`

### 结果校验结论

- `result/eval_river11_nse.py`：
  - `node11_level = 0.873332`
  - `node11_Q = -0.089159`
  - `node12_level = 0.911626`
  - `node12_Q = -0.105344`
  - `mean_nse = 0.3976138544055814`
- `tools/compare_results.py` 对：
  - `exp_opt6_branchcache_py311_40h`
  - `exp_parallel_process_fixdt_py311_40h`
  与新结果目录比较，均返回 `allclose = true`
- 关键文件：
  - `internal_node_history.csv`
  - `river11_raw_output.nc`
  - `river11_interpolated_output.nc`
  - `boundary_supercritical_counts.csv`
  - 控制点时序
  - 最终状态

全部 `max_abs = 0.0`

### 阶段结论

优化 6 可以接受：

- 这是当前最快且逐点一致的 CPU 方案
- 仍然远未达到 1 分钟目标，但已经把进程后端从“略快于串行”推进到“明显快于当前最佳串行”
- 后续若继续加速，更值得继续沿着“进程通信与结点耦合开销”这条线深入，而不是回到线程方案

## 优化 7：Cython 重写断面表标量查表链，编译加速高频 `np.interp` 热点

### 修改点

- 文件：`river_for_net.py`
  - 新增可选导入 `CrossSectionTableCython`
  - `CrossSectionTableManagerV2` 改为通过 `self._table_class` 构造断面表
  - 仅在 `ISLAM_USE_CYTHON_TABLE=1` 且扩展成功导入时启用 Cython 后端
- 新增文件：`cython_cross_section.pyx`
  - 用 Cython 重写 `CrossSectionTable` 的高频标量查表方法
  - 覆盖：
    - `get_area_by_depth`
    - `get_area_by_level`
    - `get_level_by_area`
    - `get_DEB_by_area`
    - `get_depth_by_area`
    - `get_width_by_area`
    - `get_wetted_perimeter_by_area`
    - `get_hydraulic_radius_by_area`
    - `get_press_by_area`
    - `get_value_by_area`
  - 使用手写二分查找 + 线性插值，避免热路径频繁进入 `np.interp`
  - 保留 `CrossSectionTable` 现有数组属性名，确保上层逻辑无需改动
  - 补充 `__reduce__`，使其可在持久化进程池回传 `River` 时被 pickle
- 新增文件：`build_cython_cross_section.py`
  - 提供 `build_ext --inplace` 构建入口

### 修改原因

原始 full-case `cProfile` 已明确显示：

- `numpy.lib._function_base_impl.interp` `tt=173.831 s`
- `get_width_by_area` `ct=190.685 s`
- `get_depth_by_area` `ct=177.313 s`
- `get_press_by_area` `ct=171.194 s`
- `get_hydraulic_radius_by_area` `ct=87.281 s`

这些热点都集中在断面表的高频标量查表链，而不是一次性的断面预处理逻辑。因此本轮把目标放在：

- 保持现有表结构与调用口径不变
- 只替换最热的标量插值实现
- 保留原始 Python 路径作对照与回退

### 为什么不改变计算原理

本改动没有改变：

- 控制方程
- 离散格式
- CFL 逻辑
- 边界条件处理
- 结点耦合数学含义
- 输出定义

它只是在断面表查表这一步，把原本基于 `np.interp` 的 Python/NumPy 标量查询，换成了等价的编译后线性插值实现。表数据、查表轴、返回量和调用顺序都保持不变。

### 验证命令

构建：

```bash
cd handoff_network_model_20260312
conda run -n python311 python -m pip install Cython
conda run -n python311 python build_cython_cross_section.py build_ext --inplace
```

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_cython_table_process2_10m_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_cython_table_process2_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_SAVE_CFL_HISTORY=1 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_cython_table_py311_40h_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_cython_table_py311_40h \
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

结果对比：

```bash
cd handoff_network_model_20260312
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_parallel_process_cython_table_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_tuple_py311_40h \
  result/exp_parallel_process_cython_table_py311_40h \
  --out result/exp_parallel_process_cython_table_py311_40h/compare_to_prev_best_strict.json
```

### 10 分钟 smoke 结果

- 优化 6：`6.53 s`
- 优化 7：`6.01 s`
- 绝对减少：`0.52 s`
- 相对减少：`7.96%`

`tools/compare_results.py` 严格比较下：

- `allclose = true`
- `cfl_history.csv` 完全一致
- `river11_raw_output.nc`
- `river11_interpolated_output.nc`
- 控制点
- 最终状态

均保持一致

### 实测收益

40 小时 full-case：

- 优化 6（进程，4 workers）：`612.93 s`
- 优化 7（进程，4 workers + Cython table）：`542.10 s`
- 相对优化 6：
  - 绝对减少：`70.83 s`
  - 相对减少：`11.56%`
  - 提速倍数：`1.13x`
- 相对当前最佳串行：
  - 绝对减少：`147.76 s`
  - 相对减少：`21.42%`
  - 提速倍数：`1.27x`
- 相对原始基线：
  - 绝对减少：`348.27 s`
  - 相对减少：`39.12%`
  - 提速倍数：`1.64x`

模型内部自报时间：

- 优化 6：`569.99 s`
- 优化 7：`499.99 s`
- 相对优化 6 进一步减少：`70.00 s`

### 结果校验结论

- `result/eval_river11_nse.py`：
  - `node11_level = 0.873332`
  - `node11_Q = -0.089159`
  - `node12_level = 0.911626`
  - `node12_Q = -0.105344`
  - `mean_nse = 0.3976138544055814`
- `tools/compare_results.py` 对：
  - `exp_parallel_process_tuple_py311_40h`
  - `exp_parallel_process_cython_table_py311_40h`
  返回 `allclose = true`
- 关键文件：
  - `cfl_history.csv`
  - `internal_node_history.csv`
  - `river11_raw_output.nc`
  - `river11_interpolated_output.nc`
  - `boundary_supercritical_counts.csv`
  - 控制点时序
  - 最终状态

全部通过

说明：
- `internal_node_history.csv` 的少数 `face_Q` 列存在 `1e-13` 级舍入差异，但在当前严格比较容差下仍然 `allclose = true`
- 若后续继续向更深层 Cython/C 扩展推进，可接受误差上限按用户新要求可放宽到 `1e-5`，但当前这一版实际上仍保持了严格可接受结果

### 阶段结论

优化 7 可以接受：

- 它直接命中了当前 profile 明确给出的 `np.interp` 热点簇
- 在不改河网逻辑和单河道数值原理的前提下，带来了本轮最明显的一次收益
- 当前最快严格校验通过的 CPU 方案更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`

## 优化 8：把 boundary-chi 的 general cache 查询下沉到 Cython 断面表

### 修改点

- 文件：`cython_cross_section.pyx`
  - 为 `CrossSectionTableCython` 新增 section-local `general chi` lazy cache
  - 新增：
    - `get_general_chi_by_area(...)`
    - `get_char_triplet_by_area(...)`
  - `chi(A)` 的 area 轴、积分轴和外推参数都在 Cython 对象内部构建并复用
- 文件：`river_for_net.py`
  - `_char_potential_from_general_cache()` 在 Cython table 可用时，直接走 `tbl.get_general_chi_by_area(...)`
  - `_stage_boundary_char_triplet()` 在 Cython table 可用时，直接走 `tbl.get_char_triplet_by_area(...)`
  - 原有 Python `_char_potential_cache` 路径保留，作为无扩展时的完整回退

### 修改原因

优化 7 之后，串行 + Cython table 的 10 分钟 profile 仍显示 boundary-chi 链明显偏热：

- `_resolve_stage_boundary_chi_bundle` `ct=1.979 s`
- `_stage_boundary_char_triplet` `ct=1.121 s`
- `_char_potential_from_general_cache` `ct=0.972 s`
- `OutBound_Fix_level_V3` `ct=2.863 s`
- `InBound_Fix_level_V3` `ct=1.490 s`

说明断面表几何查表已经不是主问题，但：

- `general chi` 仍在 Python 层重复做 cache 字典访问
- 仍在 `np.interp` 上消耗时间
- 仍在 `_stage_boundary_char_triplet()` 里反复调用多段小函数

因此这一轮只做一件事：

- 把 `chi(A)` 的 general-cache 构建和查询一起塞进现有 Cython table 对象
- 让边界闭合的 triplet 查询尽量在编译态完成

### 为什么不改变计算原理

本改动没有改变：

- 控制方程
- 离散格式
- CFL 序列
- 边界条件数学公式
- 结点耦合逻辑
- 输出定义

它只把已有的：

- `chi(A)` cache 构建
- `chi(A)` 插值 / 外推
- width/general/depth_ref 三元 characteristic 查询

从 Python/NumPy 小函数链，换成了等价的 Cython 实现。

### 验证命令

构建：

```bash
cd handoff_network_model_20260312
conda run -n python311 python build_cython_cross_section.py build_ext --inplace
```

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_chicache_cython_process_10m_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_chicache_cython_process_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_SAVE_CFL_HISTORY=1 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_cython_chi_py311_40h_time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
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

比较：

```bash
cd handoff_network_model_20260312
MPLCONFIGDIR=/tmp/mplconfig conda run -n python311 python result/eval_river11_nse.py result/exp_parallel_process_cython_chi_py311_40h
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_cython_table_py311_40h \
  result/exp_parallel_process_cython_chi_py311_40h \
  --out result/exp_parallel_process_cython_chi_py311_40h/compare_to_prev_best.json
```

### 10 分钟 smoke 结果

- 优化 7：`6.01 s`
- 优化 8：`5.71 s`
- 绝对减少：`0.30 s`
- 相对减少：`4.99%`

模型内部自报时间：

- 优化 7：`2.23 s`
- 优化 8：`1.95 s`

### 10 分钟串行 profile 观察

串行 + Cython table 对比优化前后：

- `_char_potential_from_general_cache`：
  - `ct=0.972 s -> 0.183 s`
- `_stage_boundary_char_triplet`：
  - `ct=1.121 s -> 0.194 s`
- `_resolve_stage_boundary_chi_bundle`：
  - `ct=1.979 s -> 1.042 s`
- `OutBound_Fix_level_V3`：
  - `ct=2.863 s -> 2.009 s`
- `InBound_Fix_level_V3`：
  - `ct=1.490 s -> 1.039 s`

说明这一轮命中的就是预期热点，而不是偶然的 wall time 摇摆。

### 实测收益

40 小时 full-case：

- 优化 7（进程，4 workers + Cython table）：`542.10 s`
- 优化 8（进程，4 workers + Cython table + chi cache）：`521.17 s`
- 相对优化 7：
  - 绝对减少：`20.93 s`
  - 相对减少：`3.86%`
  - 提速倍数：`1.04x`
- 相对当前最佳串行：
  - 绝对减少：`168.69 s`
  - 相对减少：`24.45%`
  - 提速倍数：`1.32x`
- 相对原始基线：
  - 绝对减少：`369.20 s`
  - 相对减少：`41.47%`
  - 提速倍数：`1.71x`

模型内部自报时间：

- 优化 7：`499.99 s`
- 优化 8：`478.50 s`
- 相对优化 7 进一步减少：`21.49 s`

### 结果校验结论

- `result/eval_river11_nse.py`：
  - `node11_level = 0.873332`
  - `node11_Q = -0.089159`
  - `node12_level = 0.911626`
  - `node12_Q = -0.105344`
  - `mean_nse = 0.3976138544055814`
- `tools/compare_results.py` 返回 `allclose = true`
- 关键文件：
  - `cfl_history.csv`
  - `internal_node_history.csv`
  - `river11_raw_output.nc`
  - `river11_interpolated_output.nc`
  - `boundary_supercritical_counts.csv`
  - 控制点时序
  - 最终状态

全部通过

说明：
- `internal_node_history.csv` 中少量 `face_Q` 差异仍在 `1e-13 ~ 1e-12` 以内
- 在当前严格 compare 容差下，所有关键输出依然 `allclose = true`

### 阶段结论

优化 8 可以接受：

- 它是沿着优化 7 之后留下的 boundary-chi 真热点继续往下压
- 收益不如优化 7 那么大，但是真实且稳定
- 当前最快严格校验通过的 CPU 方案更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`
