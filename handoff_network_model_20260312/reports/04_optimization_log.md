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

## 优化 9：把 general-HR 默认界面通量路径下沉到 Cython

### 修改点

- 文件：
  - `cython_cross_section.pyx`
  - `river_for_net.py`
- 修改：
  - 新增 `compute_general_hr_flux_interface(...)`
  - 在 `_compute_general_hr_interface_flux()` 里，为默认 `return_details=False` 的 general-HR 路径增加 Cython fast path
  - 保留原有 Python `state dict + details` 路径，只有诊断/明细请求时才回退

### 修改原因

优化 8 之后，演进阶段剩余的硬热点已经转到 general-HR 通量链：

- `_compute_general_hr_interface_flux`
- `_solve_general_hr_roe_flux`
- `_project_general_hr_face_state`

这条链每步、每界面都会走，但默认运行并不需要 `details`，因此 Python 侧反复构造：

- `state` 字典
- 多个临时 `np.array`
- 多次小函数分拆调用

属于可下沉的纯标量开销。

### 为什么不改变计算原理

本改动没有改变：

- 控制方程
- HR/Roe 通量公式
- entropy fix
- positivity flux control
- 结点耦合
- CFL
- 输出定义

只是把默认无诊断路径上的同一套标量公式改成 Cython 实现；当需要 `details` 时，仍走原 Python 逻辑。

### 验证命令

构建：

```bash
cd handoff_network_model_20260312
conda run -n python311 python build_cython_cross_section.py build_ext --inplace
```

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_fluxcython_process_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_fluxcython_process_10m \
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
/usr/bin/time -p -o result/exp_parallel_process_cython_flux_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_cython_flux_py311_40h \
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
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_cython_chi_py311_40h \
  result/exp_parallel_process_cython_flux_py311_40h \
  --out result/exp_parallel_process_cython_flux_py311_40h/compare_to_prev_best.json
conda run -n python311 python result/eval_river11_nse.py result/exp_parallel_process_cython_flux_py311_40h
```

### 10 分钟 smoke 结果

- 优化 8：`1.95 s`
- 优化 9：`1.94 s`
- 绝对减少：`0.01 s`
- 相对减少：`0.51%`

说明：
- 这里按当前验收口径，只看模型内部自报演进时间，不把初始化计入优化收益。

### 实测收益

40 小时 full-case：

- 优化 8：wall `521.17 s`，模型内部 `478.50 s`
- 优化 9：wall `507.12 s`，模型内部 `463.76 s`

相对优化 8：

- wall：
  - 绝对减少：`14.05 s`
  - 相对减少：`2.70%`
- 模型内部演进时间：
  - 绝对减少：`14.74 s`
  - 相对减少：`3.08%`

相对原始基线：

- wall：
  - `890.37 s -> 507.12 s`
  - 总降幅：`43.04%`
- 模型内部演进时间：
  - `832.98 s -> 463.76 s`
  - 总降幅：`44.33%`

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

全部 `max_abs = 0.0`

### 阶段结论

优化 9 可以接受：

- 收益不大，但是真实、稳定、可复现
- 它打到的是每步每界面的硬热点，而不是初始化或 I/O
- 当前最快严格校验通过的 CPU 方案仍然是：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`

## 优化 10：把默认 stage-boundary 主线路径下沉到 Cython

### 修改点

- 文件：
  - `cython_cross_section.pyx`
  - `river_for_net.py`
- 修改：
  - 新增 `compute_stage_boundary_mainline_fast(...)`
  - 为 `InBound_Fix_level_V3()` / `OutBound_Fix_level_V3()` 增加 Cython fast path
  - 仅覆盖默认高频主线路径：
    - `stage_on_face = False`
    - `use_stabilizers = False`
    - `q_hint = None`
    - `q_hint_blend = 0`
    - `q_hint_cap_factor = 0`
    - `enable_boundary_diagnostics = False`
    - `bc_use_general_chi = True`
    - `candidate_mode = guarded_clamp`
    - `guard_selector = closure_q_delta`
    - `bc_moc_with_source_stage = False`
  - 其他情况全部回退原 Python 路径

### 修改原因

优化 9 之后，演进阶段新的主热点已经更集中到 stage-boundary 闭合链：

- `OutBound_Fix_level_V3`
- `InBound_Fix_level_V3`
- `_resolve_stage_boundary_chi_bundle`
- `_prepare_stage_boundary_context`

默认 Islam workflow 里，这条链大多数时间都在走同一个“无诊断、无 stabilizer、无 q_hint、wet/subcritical”主路径，非常适合做成编译态标量闭合。

### 为什么不改变计算原理

本改动没有改变：

- 边界条件数学意义
- characteristic 闭合公式
- general-chi 选择规则
- guard 规则
- CFL
- 结点耦合
- 输出定义

它只是把默认主路径下的同一套公式换成了 Cython 标量实现。所有非主路径情况仍然沿用原逻辑。

### 验证命令

构建：

```bash
cd handoff_network_model_20260312
conda run -n python311 python build_cython_cross_section.py build_ext --inplace
```

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_boundarycython_process_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_boundarycython_process_10m \
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
/usr/bin/time -p -o result/exp_parallel_process_cython_boundary_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_cython_boundary_py311_40h \
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
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_cython_flux_py311_40h \
  result/exp_parallel_process_cython_boundary_py311_40h \
  --out result/exp_parallel_process_cython_boundary_py311_40h/compare_to_prev_best.json
conda run -n python311 python result/eval_river11_nse.py result/exp_parallel_process_cython_boundary_py311_40h
```

### 10 分钟 smoke 结果

- 优化 9：`1.94 s`
- 优化 10：`1.57 s`
- 绝对减少：`0.37 s`
- 相对减少：`19.07%`

### 实测收益

40 小时 full-case：

- 优化 9：wall `507.12 s`，模型内部 `463.76 s`
- 优化 10：wall `484.08 s`，模型内部 `441.06 s`

相对优化 9：

- wall：
  - 绝对减少：`23.04 s`
  - 相对减少：`4.54%`
- 模型内部演进时间：
  - 绝对减少：`22.70 s`
  - 相对减少：`4.89%`

相对原始基线：

- wall：
  - `890.37 s -> 484.08 s`
  - 总降幅：`45.63%`
- 模型内部演进时间：
  - `832.98 s -> 441.06 s`
  - 总降幅：`47.05%`

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

全部 `max_abs = 0.0`

### 阶段结论

优化 10 可以接受：

- 这是当前为止收益最大的单项 Cython 热点优化
- 它主要压缩的是每步高频的 stage-boundary 闭合，不涉及初始化
- 当前最快严格校验通过的 CPU 方案更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`

## 优化 11：把每步河道内部 phase barrier 合并为单次持久 worker 命令

### 修改点

- 文件：`parallel_river_pool.py`
- 新增：
  - `_advance_local_river_step()`
  - `PersistentRiverThreadPool.advance_local_step()`
  - `PersistentRiverProcessPool.advance_local_step()`
  - worker 命令 `advance_local_step`
- 文件：`Rivernet.py`
- 修改：
  - `_evolve_base_parallel_threads()`
  - `_evolve_base_parallel_process()`
- 变更内容：
  - 将每步河道内部这条固定顺序：
    - `Caculate_face_U_C`
    - `Caculate_Roe_matrix`
    - `Caculate_source_term_2`
    - `Caculate_Roe_Flux_2`
    - `Assemble_Flux_2` / `Assemble_Flux_impli_trans`
    - `Update_cell_proprity2`
    - `Save_result_per_time_step`
    - `Caculate_CFL_time_for_river_net`
  - 从多次 `pool.call_all(...)` 合并为一次 `pool.advance_local_step(...)`

### 修改原因

优化 10 之后，10 分钟并行主进程 `cProfile` 已经明确显示剩余主瓶颈不在求解公式，而在进程池 phase barrier：

- `parallel_river_pool._collect`：`2.707 s`
- `multiprocessing.connection.recv`：`2.690 s`
- `posix.read`：`2.441 s`

这些成本主要来自“每个时间步把同一条河道的本地推进拆成多次 worker 往返”。而在边界和结点同步完成之后，河道内部推进到 CFL 计算这一段是完全局部的：

- 不依赖其他河道状态
- 不依赖新的结点交换
- 只要求保持单河道内部调用顺序不变

因此可以把这段顺序计算压缩成一次持久 worker 命令，减少 IPC 次数，而不改变单河道的计算逻辑。

### 为什么不改变计算原理

本改动没有改变：

- 控制方程
- Roe 通量
- 源项与摩阻更新
- 边界条件数学公式
- 结点耦合方式
- CFL 选取口径
- 输出定义

它只把“原本分散的、同一河道内固定顺序调用”打包到了 worker 内顺序执行。

每条河道内部仍然严格按原顺序执行：

1. `Caculate_face_U_C`
2. `Caculate_Roe_matrix`
3. `Caculate_source_term_2`
4. `Caculate_Roe_Flux_2`
5. `Assemble_Flux_2` / `Assemble_Flux_impli_trans`
6. `Update_cell_proprity2`
7. `Save_result_per_time_step`
8. `Caculate_CFL_time_for_river_net`

河网层仍然保持：

- 先统一做边界/结点耦合
- 再让各河道独立推进
- 每步结束后再统一取 CFL

所以数学含义与串行/旧并行路径一致。

### 验证命令

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_fusedstep_process_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_fusedstep_process_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

10 分钟主进程 profile：

```bash
env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_profile_fused_process_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  /usr/bin/time -p conda run -n python311 python -m cProfile \
  -o result/tmp_profile_fused_process_10m.prof Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_fusedstep_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_fusedstep_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

比较：

```bash
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_cython_boundary_py311_40h \
  result/exp_parallel_process_fusedstep_py311_40h \
  --out result/exp_parallel_process_fusedstep_py311_40h/compare_to_prev_best.json

conda run -n python311 python result/eval_river11_nse.py \
  result/exp_parallel_process_fusedstep_py311_40h
```

### 10 分钟 smoke 结果

- 优化 10：`1.57 s`
- 优化 11：`1.45 s`
- 绝对减少：`0.12 s`
- 相对减少：`7.64%`

wall time：

- 优化 10：`6.09 s`
- 优化 11：`5.40 s`
- 绝对减少：`0.69 s`
- 相对减少：`11.33%`

10 分钟主进程 profile 变化：

- `recv` 调用次数：`15886 -> 11361`
- `posix.read`：`2.441 s -> 2.140 s`
- `_collect`：`2.707 s -> 2.346 s`

### 实测收益

40 小时 full-case：

- 优化 10：wall `484.08 s`，模型内部 `441.06 s`
- 优化 11：wall `446.50 s`，模型内部 `404.22 s`

相对优化 10：

- wall：
  - 绝对减少：`37.58 s`
  - 相对减少：`7.76%`
- 模型内部演进时间：
  - 绝对减少：`36.84 s`
  - 相对减少：`8.35%`

相对原始基线：

- wall：
  - `890.37 s -> 446.50 s`
  - 总降幅：`49.85%`
- 模型内部演进时间：
  - `832.98 s -> 404.22 s`
  - 总降幅：`51.47%`

### 结果校验结论

- `result/eval_river11_nse.py`：
  - `node11_level = 0.873332`
  - `node11_Q = -0.089159`
  - `node12_level = 0.911626`
  - `node12_Q = -0.105344`
  - `mean_nse = 0.3976138544055814`
- `tools/compare_results.py` 返回 `allclose = true`
- 关键文件：
  - `internal_node_history.csv`
  - `river11_raw_output.nc`
  - `river11_interpolated_output.nc`
  - `boundary_supercritical_counts.csv`
  - 控制点时序
  - 最终状态

全部 `max_abs = 0.0`

### 阶段结论

优化 11 可以接受：

- 它不碰单河道数值公式，收益主要来自减少 phase barrier 与 worker 往返
- 这是当前为止收益最大的“纯并行调度层”优化
- 当前最快严格校验通过的 CPU 方案更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`

## 优化 12：压缩内部结点迭代阶段的并行 snapshot 负载

### 修改点

- 文件：`parallel_river_pool.py`
- 修改：
  - `_river_interface_snapshot()` 新增 `mode='compact'`
  - `call_batch_and_interface_snapshots()` 支持 `snapshot_mode`
  - process/thread backend 都支持 compact snapshot
- 文件：`Rivernet.py`
- 新增：
  - `_parallel_can_use_compact_snapshots()`
- 修改：
  - `_update_boundary_conditions_parallel()` 在满足当前默认内部结点配置时：
    - 外边界与内部结点迭代阶段使用 compact snapshot
    - 最终记录 `internal_node_history.csv` 前仍强制取 full snapshot
  - `_parallel_node_average_level_at_real_cell()`
  - `_parallel_node_average_level_at_ghost_cell()`
  - `_parallel_node_mass_residual()`
  - `_parallel_node_ac()`
  - `_build_parallel_internal_level_ops()` 去掉了 `0.0 * velocity^2 / (2g)` 的死计算

### 修改原因

优化 11 之后，主进程剩余大头已经集中到 `_update_boundary_conditions_parallel()`。

在当前 Islam 默认 process 配置下，内部结点迭代真正需要的字段非常少：

- 初值预测：`ghost_level / cell_level`
- 残差：`ghost_Q`
- `paper Ac`：`ghost_S / ghost_width / ghost_Q`

但旧实现每次迭代都要把每条河道两端的 12 字段 full snapshot 全部回传，包括：

- `cell_Q`
- `boundary_face_level`
- `boundary_face_discharge`
- `boundary_face_area`
- `boundary_face_width`

这些字段对当前内部结点迭代并不参与计算，只在最终 history 写出时才需要。因此可以把“迭代阶段的中间快照”瘦身成最小字段集，减少 IPC 体积。

### 为什么不改变计算原理

本改动没有改变：

- 结点残差公式
- `paper Ac` 公式
- 固定水位边界闭合
- 河道推进顺序
- CFL
- 输出定义

它只改变“结点迭代阶段 worker 回传的数据载荷”，不改变回传数据的数学含义。

并且：

- 只有在当前默认内部结点配置下才启用 compact snapshot
- 其他配置继续走 full snapshot 旧路径
- 最终 history 记录前仍然强制取 full snapshot，所以输出文件完全不变

### 验证命令

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_compactsnap_process_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_compactsnap_process_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_compactsnap_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_compactsnap_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

比较：

```bash
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_fusedstep_py311_40h \
  result/exp_parallel_process_compactsnap_py311_40h \
  --out result/exp_parallel_process_compactsnap_py311_40h/compare_to_prev_best.json

conda run -n python311 python result/eval_river11_nse.py \
  result/exp_parallel_process_compactsnap_py311_40h
```

### 10 分钟 smoke 结果

- 优化 11：`1.45 s`
- 优化 12：`1.38 s`
- 绝对减少：`0.07 s`
- 相对减少：`4.83%`

### 实测收益

40 小时 full-case：

- 优化 11：wall `446.50 s`，模型内部 `404.22 s`
- 优化 12：wall `442.12 s`，模型内部 `399.33 s`

相对优化 11：

- wall：
  - 绝对减少：`4.38 s`
  - 相对减少：`0.98%`
- 模型内部演进时间：
  - 绝对减少：`4.89 s`
  - 相对减少：`1.21%`

相对原始基线：

- wall：
  - `890.37 s -> 442.12 s`
  - 总降幅：`50.34%`
- 模型内部演进时间：
  - `832.98 s -> 399.33 s`
  - 总降幅：`52.06%`

### 结果校验结论

- `result/eval_river11_nse.py`：
  - `node11_level = 0.873332`
  - `node11_Q = -0.089159`
  - `node12_level = 0.911626`
  - `node12_Q = -0.105344`
  - `mean_nse = 0.3976138544055814`
- `tools/compare_results.py` 返回 `allclose = true`
- 关键文件：
  - `internal_node_history.csv`
  - `river11_raw_output.nc`
  - `river11_interpolated_output.nc`
  - `boundary_supercritical_counts.csv`
  - 控制点时序
  - 最终状态

全部 `max_abs = 0.0`

### 阶段结论

优化 12 可以接受：

- 它是沿着优化 11 剩下的 IPC 热点继续压 payload
- 收益不大，但仍然稳定、严格一致
- 当前最快严格校验通过的 CPU 方案更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`

## 优化 13：worker 侧聚合内部结点接口量

提交：`待提交`

### 修改内容

- `parallel_river_pool.py`
  - 新增 `NODE_AGG_*` 聚合字段常量
  - 新增 `_node_aggregate_from_specs()`，worker 侧直接按结点累计：
    - 相邻实格平均水位所需和/计数
    - ghost 平均水位所需和/计数
    - 结点质量残差
    - paper-AC 导数近似
  - 新增 `call_batch_and_node_aggregates()`，在同一次 worker 往返里：
    - 先执行边界施加
    - 再只返回每个 internal node 的紧凑聚合量
- `Rivernet.py`
  - 新增 `_parallel_node_*_from_aggregates()` 一组 helper
  - 新增 `_parallel_internal_node_aggregate_specs()` 缓存，把 internal node 对应的 river 端点规格固定下来
  - `_update_boundary_conditions_parallel()` 在默认 internal node 配置下改为：
    - 外边界阶段直接返回 internal node 聚合量
    - internal iteration 每轮只返回聚合量
    - 仅在最终记录 `internal_node_history.csv` 前再强制取一次 full snapshot

### 原理说明

这一步不改变：

- 外边界 / 内部边界公式
- 结点牛顿迭代的数学含义
- 单河道边界处理方式
- 时间推进顺序
- CFL
- 输出文件定义

它只把“内部结点迭代阶段从 worker 回传的接口信息”从逐河道 compact snapshot 改成逐结点聚合量。

### 验证命令

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_nodeagg_process_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_nodeagg_process_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_parallel_process_nodeagg_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_parallel_process_nodeagg_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

比较：

```bash
conda run -n python311 python tools/compare_results.py \
  result/exp_parallel_process_compactsnap_py311_40h \
  result/exp_parallel_process_nodeagg_py311_40h \
  --out result/exp_parallel_process_nodeagg_py311_40h/compare_to_prev_best.json

conda run -n python311 python result/eval_river11_nse.py \
  result/exp_parallel_process_nodeagg_py311_40h
```

### 10 分钟 smoke 结果

- 优化 12：`1.38 s`
- 优化 13：`1.31 s`
- 绝对减少：`0.07 s`
- 相对减少：`5.07%`

### 实测收益

40 小时 full-case：

- 优化 12：wall `442.12 s`，模型内部 `399.33 s`
- 优化 13：wall `427.97 s`，模型内部 `385.73 s`

相对优化 12：

- wall：
  - 绝对减少：`14.15 s`
  - 相对减少：`3.20%`
- 模型内部演进时间：
  - 绝对减少：`13.60 s`
  - 相对减少：`3.41%`

相对原始基线：

- wall：
  - `890.37 s -> 427.97 s`
  - 总降幅：`51.93%`
- 模型内部演进时间：
  - `832.98 s -> 385.73 s`
  - 总降幅：`53.69%`

### 结果校验结论

- `result/eval_river11_nse.py`：
  - `node11_level = 0.873332`
  - `node11_Q = -0.089159`
  - `node12_level = 0.911626`
  - `node12_Q = -0.105344`
  - `mean_nse = 0.3976138544055814`
- `tools/compare_results.py` 返回 `allclose = true`
- `river11_raw_output.nc`
- `river11_interpolated_output.nc`
- 控制点时序
- 最终状态

以上全部 `max_abs = 0.0`

- `internal_node_history.csv`
  - 少数 `face_level` / `face_Q` 列出现 `1e-16 ~ 2e-13` 量级差异
  - 原因是 worker 侧先做局部结点聚合，再由主进程按 worker 顺序合并，浮点加和分组与逐支路 snapshot 求和略有不同
  - 当前 compare 仍为 `allclose = true`

### 阶段结论

优化 13 可以接受：

- 它继续压缩内部结点阶段的 worker 回传 payload
- 在不改数值链的前提下继续降低了 `_update_boundary_conditions_parallel()` 成本
- 当前最快严格 compare 通过的 CPU 方案更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`

## 优化 14：按可选间隔保存输出，默认对齐 yield 时刻

### 修改内容

- 单河道保存链改为“调度式保存”：
  - 新增 `configure_save_scheduler()`
  - 新增 `maybe_save_result_per_time_step()`
- 河网层不再把“每个子步都构建一帧 xarray”当成默认行为。
- 默认保存间隔改为：
  - 若显式设置 `ISLAM_SAVE_INTERVAL`，按该秒数保存
  - 否则默认按 `yield_step` 保存
- 仍保留：
  - 初始时刻一帧
  - 最终时刻一帧
  - 原始 `raw_output.nc` / `interpolated_output.nc` 文件格式和变量定义

### 影响范围

- [river_for_net.py](/home/xin/River_net_parallel/handoff_network_model_20260312/river_for_net.py)
- [parallel_river_pool.py](/home/xin/River_net_parallel/handoff_network_model_20260312/parallel_river_pool.py)
- [Rivernet.py](/home/xin/River_net_parallel/handoff_network_model_20260312/Rivernet.py)
- [Islam.py](/home/xin/River_net_parallel/handoff_network_model_20260312/Islam.py)

### 设计说明

这一步是按用户要求接受的输出行为调整：

- 不改变数值核
- 不改变时间推进
- 不改变边界/耦合
- 只改变“什么时候把当前状态封装成 xarray 写入 `ds_list`”

旧逻辑：

- `river11_raw_output.nc` 在 40h full-case 中保存了 `29969` 帧
- worker 每个子步都构建一次 xarray

新逻辑：

- 默认只在 `yield_step` 对齐时刻保存
- 并保留 `t=0` 与最终时刻
- 40h full-case 中 `river11_raw_output.nc` 降为 `81` 帧

### 验证命令

10 分钟 smoke：

```bash
/usr/bin/time -p -o result/tmp_saveinterval_process_10m/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/tmp_saveinterval_process_10m \
  ISLAM_SIM_END_TIME='2024-01-01 00:10:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

40 小时 full-case：

```bash
/usr/bin/time -p -o result/exp_saveinterval_yield_process_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_saveinterval_yield_process_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  ISLAM_USE_PARALLEL=1 \
  ISLAM_PARALLEL_BACKEND=process \
  ISLAM_N_WORKERS=4 \
  ISLAM_USE_CYTHON_TABLE=1 \
  conda run -n python311 python Islam.py
```

### 10 分钟 smoke 结果

- 旧版逐子步保存：`1.28 s`
- 新版按间隔保存：`1.23 s`
- 绝对减少：`0.05 s`
- 相对减少：`3.91%`

输出形态：

- `river11_raw_output.nc`：`181 -> 2` 帧（`t=0`, `t=600s`）
- `river11_interpolated_output.nc`：`11` 帧（`0:60:600`）

### 实测收益

40 小时 full-case：

- 旧版：wall `427.97 s`，模型内部 `385.73 s`
- 新版：wall `158.33 s`，模型内部 `151.00 s`

相对旧版：

- wall：
  - 绝对减少：`269.64 s`
  - 相对减少：`63.01%`
- 模型内部演进时间：
  - 绝对减少：`234.73 s`
  - 相对减少：`60.86%`

相对原始基线：

- wall：
  - `890.37 s -> 158.33 s`
  - 总降幅：`82.22%`
- 模型内部演进时间：
  - `832.98 s -> 151.00 s`
  - 总降幅：`81.87%`

### 结果校验结论

这一步不再适合直接沿用旧版 `tools/compare_results.py` 做“目录全量 allclose”，原因是：

- `raw_output.nc` 的时间维按设计变稀疏了
- `interpolated_output.nc` 现在从 `t=0` 对齐开始，时间轴定义也按要求变了

因此本次接受口径改为：

- `internal_node_history.csv` 逐点一致：
  - `max_abs = 0.0`
- `river11_raw_output.nc` 最后一帧逐点一致：
  - `depth/level/U/Q` 全部 `max_abs = 0.0`
- `boundary_supercritical_counts.csv` 一致
- 数值核没有改动，仅保存时刻改变

补充说明：

- `result/eval_river11_nse.py` 在新输出口径下得到：
  - `node11_level = 0.865799`
  - `node11_Q = -0.003330`
  - `node12_level = 0.913786`
  - `node12_Q = 0.020118`
  - `mean_nse = 0.449093342258747`
- 这组 NSE 改善主要反映“插值时间轴从 `t=0` 对齐”的输出口径变化，不应误读为数值核本身改变。

### 阶段结论

优化 14 可以接受：

- 它准确实现了“默认按 yield 时刻保存，而不是每子步构建 xarray”的新要求
- 它显著降低了 worker 侧保存开销
- 它不改变数值结果，只改变输出抽样节奏
- 当前推荐 CPU 路径更新为：
  - `process backend`
  - `4 workers`
  - `ISLAM_USE_CYTHON_TABLE=1`
  - `ISLAM_SAVE_INTERVAL` 留空（默认按 `yield_step` 保存）
