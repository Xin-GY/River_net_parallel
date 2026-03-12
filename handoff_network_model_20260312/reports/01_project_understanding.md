# A. 项目理解

## 1. 项目结构

```text
handoff_network_model_20260312/
|-- README.md
|-- FILE_MAP.csv
|-- Islam.py
|-- Rivernet.py
|-- river_for_net.py
|-- config.py
|-- persistent_interpolator.py
|-- docs/
|   |-- START_HERE.md
|   |-- CURRENT_STATUS.md
|   |-- RUNBOOK.md
|   `-- CHANGES_IN_THIS_PACK.md
|-- bound/
|   |-- Islam_Q_In.csv
|   `-- Islam_level_out.csv
|-- result/
|   |-- Islam_real_data/
|   |   |-- node11_level.csv
|   |   |-- node11_Q.csv
|   |   |-- node12_level.csv
|   |   `-- node12_Q.csv
|   |-- eval_river11_nse.py
|   |-- package_river11_report.py
|   |-- river11_compare_utils.py
|   `-- exp_handoff_pkg_smoke_1h/
|-- artifacts/
|   |-- latest_handoff/
|   `-- historical_best/
|-- examples/
|   |-- run_islam_40h_current.sh
|   `-- evaluate_and_package.sh
|-- tool_fun/
|   `-- section_偏移.py
`-- reports/
    `-- 01_project_understanding.md
```

## 2. 入口脚本

- 命令行案例入口：`Islam.py`
- 类入口：
  - 河网层：`Rivernet.py::Rivernet`
  - 单河道层：`river_for_net.py::River`
- 对比与打包入口：
  - `result/eval_river11_nse.py`
  - `result/package_river11_report.py`

`Islam.py` 当前不是“参数解析 + main()”风格，而是顶层脚本执行风格。导入后会直接构造案例、创建 `Rivernet`、施加边界并运行 `for t in net.Evolve(1800)`。

## 3. 主要类与职责

### `Islam.py`

- 定义整个 Islam 河网案例的几何、断面、粗糙率、拓扑。
- 从环境变量读取运行开关。
- 构造：
  - `model_data`
  - 各河道 `river_data_*`
  - 各河道 `section_data_*`
  - 各河道 `section_pos_*`
  - 总拓扑 `top`
- 通过 `PersistentLinearInterpolator` 读取外边界时序：
  - `bound/Islam_Q_In.csv`
  - `bound/Islam_level_out.csv`
- 创建 `net = Rivernet(top, model_data)`。
- 调用：
  - `configure_net_options(net)`
  - `apply_boundaries(net)`
  - `initialize_rivers(net)`
- 可选 warmup 后复制末态。
- 主计算入口：
  - `for t in net.Evolve(1800): net.print_evolve_info()`
- 运行后写出：
  - `boundary_supercritical_counts.csv`

### `Rivernet.py::Rivernet`

- 把 `top` 转成 `networkx.DiGraph`。
- 为每条 edge 深拷贝参数后创建 `River(...)` 实例。
- 管理节点分类、边界条件、内部节点耦合、全局 CFL、结果保存。
- 以“河网主控器”的角色逐步调用所有河道内核。

### `river_for_net.py::River`

- 单河道有限体积求解器。
- 负责：
  - 均匀单元/ghost 布置
  - 断面表构建
  - 水面初始化
  - 面量、波速、Roe 矩阵、源项、通量、更新
  - 河道级 CFL
  - 每步结果缓存与最终 NetCDF 输出
- `River` 虽继承 `multiprocessing.Process`，但在当前 Islam 主链中没有启动子进程，当前运行路径是纯串行、同进程对象调用。

### `persistent_interpolator.py::PersistentLinearInterpolator`

- 负责把边界 CSV 清洗为单调 `x/y`，落本地 cache，再做线性插值。
- 属于外边界读取加速层，不参与 PDE 主求解。

## 4. 案例对象创建链

1. `Islam.py` 定义 `model_data`。
2. `Islam.py` 定义 14 条河道对应的 `river_data_* / section_data_* / section_pos_*`。
3. `Islam.py` 定义 `top = {(u, v): {...}}`。
4. `Islam.py` 构造 `net = Rivernet(top, model_data)`。
5. `Rivernet.__init__()` 调 `Create_Rivernet()`。
6. `Create_Rivernet()` 对每条 edge：
   - `deepcopy(info['river_data'])`
   - `deepcopy(info['section_data'])`
   - `deepcopy(info['section_pos'])`
   - 创建 `River(river_data, section_data, section_pos, model_data)`
   - 挂到 `self.G.add_edge(u, v, river=river, name=info['name'])`

## 5. 输入数据如何传入

### 边界条件

- 上游 7 个外部入点：`n1` 到 `n7`
  - 类型：`flow`
  - 来源：`bound/Islam_Q_In.csv`
- 下游外部出点：`n14`
  - 类型：`fix_level`
  - 来源：`bound/Islam_level_out.csv`
- `Islam.py::apply_boundaries()` 调 `net.set_boundary(...)`
- 每个时间步由 `Rivernet.Update_external_boundary_conditions_V2()` 实际施加到各相邻 `River`

### 初始条件

- 默认统一初始水位：`init_level`
- 在 `Islam.py::initialize_rivers()` 中对每条河道执行 `river.Set_init_water_level(init_level)`
- 可选按经验公式给各 branch 赋初始流量猜测：`ISLAM_INIT_Q_MODE=steady_guess`
- 可选 warmup：
  - 再创建一个 `Rivernet`
  - 先跑一段
  - 用 `copy_warmup_state()` 把末态复制回正式模型

### 断面与几何

- 每条河道在 `Islam.py` 顶层硬编码 `river_data_*` 与 `section_data_*`
- `build_local_section_pos()` 为 Fine 断面重构补齐 `section_pos`
- `maybe_adjust_sections()` 可按河床高程口径对断面整体平移

### 拓扑关系

- `top` 字典的 key 是 `(from_node, to_node)`，value 包含：
  - `name`
  - `river_data`
  - `section_data`
  - `section_pos`
  - `manning`

## 6. 主调用链

### 案例构建

`Islam.py`
-> 创建 `top`
-> `net = Rivernet(top, model_data)`
-> `configure_net_options(net)`
-> `apply_boundaries(net)`
-> `initialize_rivers(net)`
-> 可选 warmup
-> `net.Evolve(1800)`

### 河网初始化

`Rivernet.Evolve(yield_step)`
-> 可选 `Fine_cell_property_net()`
-> `Init_water_surface_net()`
-> `Init_cell_property_net()`
-> `Save_basic_data_net()`
-> `Caculate_global_CFL()`
-> `_evolve_base(yield_step)`

### 每个时间步

`Rivernet._evolve_base()`
-> `Set_global_time_step(self.DT)`
-> `Update_boundary_conditions()`
-> `Caculate_face_U_C_net()`
-> `Caculate_Roe_matrix_net()`
-> `Caculate_Source_term_net()`
-> `Caculate_Roe_flux_net()`
-> `Assemble_flux_net()` 或隐式分支
-> `Update_cell_property_net()`
-> `Save_step_result_net()`
-> `Caculate_global_CFL()`
-> 更新下一步 `DT`

### 单河道一步内部

网络层不是调用 `River.Evolve()`，而是显式分拆调用 `River` 的内核函数：

- `Caculate_face_U_C`
- `Caculate_Roe_matrix`
- `Caculate_source_term_2`
- `Caculate_Roe_Flux_2`
- `Assemble_Flux_2`
- `Update_cell_proprity2`

这意味着河网层对河道步进拥有完整调度控制权。

## 7. 时间推进流程

### 时间由谁控制

- 全局时间推进由 `Rivernet._evolve_base()` 控制。
- 全网统一 `DT`，由每条河道各自算 CFL 后取全局最小值得到。
- `yield_step=1800` 只是对外回报节奏，不是内部真实时间步。

### 关键细节

- `Rivernet.Set_global_time_step(dt)` 会对每条河道调用 `river.set_next_dt(dt)`。
- `river.set_next_dt(dt)` 当前不仅设置 `DT`，还会把该河道 `current_sim_time += DT`。
- 然后 `Rivernet` 自己也会增加 `current_sim_time += DT`。
- 这一点后续若做性能优化必须保持现有行为，不可“顺手纠正”，否则属于逻辑变化。

## 8. 河网耦合流程

### 外边界

每步先由 `Update_external_boundary_conditions_V2()` 根据当前时刻边界值，对与外部节点相连的河段端点施加：

- 上游 `flow`：
  - 优先 `InBound_In_Q2`
  - 否则 `InBound_In_Q`
- 下游 `fix_level`：
  - `OutBound_Fix_level_V3` 或 V2

### 内部节点

每步紧接着执行 `Update_internal_boundary_conditions()`：

1. 先给每个内部节点估计当前水位初值。
2. 用迭代或耦合牛顿求各节点水位，使节点净流量残差接近 0。
3. 通过 `_apply_internal_node_levels()` / `Apply_node_target_level_V4()` 把统一节点水位施加到相连支路鬼格。
4. 最终统一再施加一次，保证后续通量计算使用一致边界。

### 依赖关系结论

- 当前结构不是“所有河道先独立推进完，再统一交换边界”。
- 真实顺序是：
  - 先全网边界交换与节点耦合
  - 再各河道做本步 Roe/源项/更新
- 因此“每步末尾统一交换边界”的假设不成立。
- 但在边界条件已经施加完成之后，下列 per-river 计算在数学上看起来是局部的：
  - `Caculate_face_U_C_net`
  - `Caculate_Roe_matrix_net`
  - `Caculate_Source_term_net`
  - `Caculate_Roe_flux_net`
  - `Assemble_flux_net`
  - `Update_cell_property_net`
- 是否适合并行，必须以后续 profile 和数据交换成本来定，不能现在直接假定。

## 9. 输出逻辑

### 运行中输出

- `Save_step_result_net()` 逐河道调用 `River.Save_result_per_time_step()`
- 每次把当前时刻的 `depth / level / U / Q` 切片复制成一个 `xarray.Dataset`，追加到 `river.ds_list`

### 运行结束输出

- `Rivernet.Resample_and_Save_result_net()`
  - 逐河道调用 `River.Check_Resample_and_Save_Output_result()`
  - 写出：
    - `{river}_raw_output.nc`
    - `{river}_interpolated_output.nc`
- `Rivernet.Save_internal_node_history()`
  - 写出 `internal_node_history.csv`
- `Islam.py` 末尾
  - 写出 `boundary_supercritical_counts.csv`
- `configure_net_options(export_png=True)`
  - 在输出目录写 `net.png`

### 当前 handoff 的基准验收输出

当前 docs 指向的基准运行命令为：

```bash
MPLCONFIGDIR=/tmp/mplconfig \
ISLAM_OUTPUT_PATH=result/exp_handoff_run \
ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
ISLAM_OUTPUT_RIVERS=river11 \
ISLAM_USE_FINE_INTERPOLATION=0 \
conda run -n python310 python Islam.py
```

所以当前 handoff 文档中的基准输出集合是：

- `result/exp_handoff_run/river11_raw_output.nc`
- `result/exp_handoff_run/river11_interpolated_output.nc`
- `result/exp_handoff_run/internal_node_history.csv`
- `result/exp_handoff_run/boundary_supercritical_counts.csv`
- `result/exp_handoff_run/net.png`

并不是“全河网所有河道都写盘”的基准模式；但功能上仍保留 `output_river_names=None` 时全河网输出的能力，后续优化不得破坏这一能力。

## 10. 基准结果位置与比较口径

### 当前 handoff 内置最佳基准

- `artifacts/latest_handoff/`
- `artifacts/historical_best/`

两者当前逐文件完全一致。

### 基准比较字段

`result/river11_compare_utils.py` 明确只比较 4 条序列：

- `node11_level`
- `node11_Q`
- `node12_level`
- `node12_Q`

对应提取方式：

- 数据源：`river11_interpolated_output.nc`
- 取点：
  - `space=0` 对应 `node11`
  - `space=11` 对应 `node12`
- 变量：
  - `level`
  - `Q`

### 基准比较格式

- 参考观测：CSV
- 模型主结果：NetCDF
- 评估输出：
  - `nse_summary.csv`
  - `node*_sim_raw.csv`
  - `node*_real.csv`
  - `node*_compare_on_real_time.csv`
  - `*_compare.png`
  - `river11_four_curves_compare.png`
  - `report_meta.json`

### 比较时序

- `river11_interpolated_output.nc` 先重采样到统一输出步长。
- 之后再插值到观测 CSV 的时间坐标。
- 评估不是“每个内部时间步逐点比较”，而是“每个输出步重采样后，对观测时刻比较”。

## 11. 哪些步骤严格串行

- `Islam.py` 顶层案例构造
- `Rivernet._evolve_base()` 的全局时间循环
- 每步的 `Update_boundary_conditions()`
- 内部节点的耦合迭代和统一施加
- 全局 CFL 最小值汇总
- 结束时的结果重采样和写盘

## 12. 哪些部分理论上可能并行

前提是该步边界已经施加完成，且不改变浮点结果顺序：

- 各河道的 `Caculate_face_U_C`
- 各河道的 `Caculate_Roe_matrix`
- 各河道的 `Caculate_source_term_2`
- 各河道的 `Caculate_Roe_Flux_2`
- 各河道的 `Assemble_Flux_2`
- 各河道的 `Update_cell_proprity2`
- 各河道的 `Caculate_CFL_time_for_river_net`

但当前不能直接认定“值得并行”，原因有三点：

1. 内部节点耦合仍然强串行。
2. `River` 对象很大，若跨进程传输会有明显 pickle 成本。
3. 当前代码里已经有不少历史多进程痕迹，但主链并未实际使用，说明之前并行化可能未真正落地。

## 13. 初步热点判断

仅基于静态阅读，不代替 profile：

### 可能的计算热点

- `Update_internal_boundary_conditions()`
  - 每步每内部节点多次迭代
  - 每次迭代会频繁访问多河道端点状态
- `River` 的 Roe 主链
  - `Caculate_face_U_C`
  - `Caculate_Roe_matrix`
  - `Caculate_source_term_2`
  - `Caculate_Roe_Flux_2`
  - `Assemble_Flux_2`
  - `Update_cell_proprity2`
- 输出缓存
  - `Save_result_per_time_step()` 每次创建新的 `xarray.Dataset`
  - 末尾 `xr.concat + interp + to_netcdf`

### 明显的 Python 工程开销候选

- `Rivernet` 中大量 `for _, _, data in self.G.edges(data=True)` 的重复遍历
- `call_river_function_by_name()` 的 `hasattr/getattr/callable` 动态分发
- `Create_Rivernet()` 的深拷贝
- 每步/每迭代深层属性访问
- 输出阶段反复构造小 `xarray.Dataset`

### 可能但尚未证实的多进程障碍

- `River` 继承 `Process`，但实际以普通对象使用
- `river_for_net.py` 导入了 `ProcessPoolExecutor` 和 `Queue`，主链未使用
- 这意味着若要加常驻 worker，需要重新梳理对象驻留位置，而不是直接把现有对象塞给 `ProcessPoolExecutor`

## 14. 绝对不能改动逻辑的清单

后续优化必须保持以下逻辑不变：

- 控制方程
- 单河道有限体积离散形式
- Roe/源项/更新的数学口径
- 内外边界条件的数学含义
- 内部节点耦合的残差定义与求解目标
- 全局时间推进策略
- CFL 取全网最小值的规则
- 结果输出字段：
  - `depth`
  - `level`
  - `U`
  - `Q`
- 当前输出文件生成逻辑
- `ISLAM_OUTPUT_RIVERS` 的现有行为
- `net.png`、`internal_node_history.csv`、`boundary_supercritical_counts.csv` 的生成能力
- warmup 路径和末态复制逻辑
- 所有现有环境变量开关的对外语义

特别注意：

- 不能因为优化而减少内部时间步数。
- 不能降低输出频率来伪装提速。
- 不能移除现有输出能力，即使基准 run 只导出 `river11`。
- 不能“顺手修正”任何现有数值/时间累计行为，除非单独作为逻辑修复且不进入性能方案。

## 15. 下一阶段执行计划

第 2 阶段将严格按当前 handoff 既有运行方式建立 baseline：

1. 在用户指定的 `conda` `python311` 环境中检查依赖是否齐全。
2. 用当前 handoff 的原始串行逻辑跑通案例。
3. 记录：
   - 运行命令
   - Python 版本
   - CPU 核心数
   - 原始总耗时
   - 基准结果目录
4. 对结果执行评估与打包，确认与 `artifacts/latest_handoff` 的一致性基线。

本报告阶段只做阅读与建模，不做任何计算逻辑改动。
