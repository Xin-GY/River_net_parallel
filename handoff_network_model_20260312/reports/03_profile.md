# C. 热点分析

## 1. 剖析方法

在 `handoff_network_model_20260312/` 目录下，对原始 40h 串行案例执行 full-case `cProfile`：

```bash
/usr/bin/time -p -o result/exp_profile_py311_40h/time.txt \
  env MPLCONFIGDIR=/tmp/mplconfig \
  ISLAM_OUTPUT_PATH=result/exp_profile_py311_40h \
  ISLAM_SIM_END_TIME='2024-01-02 16:00:00' \
  ISLAM_OUTPUT_RIVERS=river11 \
  ISLAM_USE_FINE_INTERPOLATION=0 \
  conda run -n python311 python -m cProfile \
    -o result/profile_baseline_py311_40h.prof \
    Islam.py \
  > result/exp_profile_py311_40h/run.log 2>&1
```

说明：

- 仍是原始串行逻辑。
- 未插入任何手改计时代码。
- `line_profiler` 在 `python311` 环境中不存在；当前未安装，因为 full-case `cProfile` 已足够定位函数级热点。

## 2. profile 运行结果

### wall time

`time.txt`：

```text
real 1933.69
user 1932.85
sys 2.22
```

### 模型内部自报

`run.log` 末尾：

```text
共计算 29969 步，总耗时: 1852.29 秒
```

### 与无 profile 基线关系

- 无 profile 基线 wall time：`890.37 s`
- profile wall time：`1933.69 s`
- 放大倍数：约 `2.17x`

因此下文应优先解读“占比”和“相对排序”，不直接拿 profile 绝对秒数当真实运行时间。

## 3. profile 结果正确性

profile 版结果重新执行 `result/eval_river11_nse.py` 后，四条曲线仍为：

```text
node11_level =  0.873332
node11_Q     = -0.089159
node12_level =  0.911626
node12_Q     = -0.105344
mean_nse     =  0.3976138544055814
```

说明 profile 本身没有改变结果。

## 4. 函数级热点

### cumulative time 前列

```text
Update_boundary_conditions            ct= 969.658 s
Update_internal_boundary_conditions   ct= 904.543 s
_apply_internal_node_levels           ct= 848.134 s
Apply_node_target_level_V4            ct= 847.054 s
call_river_function_by_name           ct= 824.631 s
OutBound_Fix_level_V3                 ct= 541.332 s
_compute_general_hr_interface_flux    ct= 443.146 s
Caculate_Roe_flux_net                 ct= 380.787 s
_refresh_cell_state                   ct= 345.660 s
_caculate_roe_flux_general_hr         ct= 307.753 s
InBound_Fix_level_V3                  ct= 273.261 s
_resolve_stage_boundary_chi_bundle    ct= 253.013 s
_append_stage_boundary_record         ct= 243.581 s
Update_cell_property_net              ct= 242.097 s
Update_cell_proprity2                 ct= 239.678 s
_solve_general_hr_roe_flux            ct= 206.270 s
_peek_interface_flux_for_diagnostics  ct= 198.988 s
get_width_by_area                     ct= 190.685 s / 159.617 s
_stage_boundary_char_triplet          ct= 168.268 s
Assemble_flux_net                     ct= 151.763 s
```

### internal time 前列

```text
numpy.lib._function_base_impl.interp  tt=173.831 s
_solve_general_hr_roe_flux            tt=111.373 s
numpy._core._multiarray_umath.interp  tt=108.822 s
_refresh_cell_state                   tt= 87.239 s
get_width_by_area                     tt= 50.306 s / 26.648 s
_char_potential_from_general_cache    tt= 37.310 s
_solve_rectangular_hr_roe_flux        tt= 35.379 s
_append_stage_boundary_record         tt= 31.250 s
_apply_explicit_friction_substep      tt= 28.877 s
_prepare_stage_boundary_context       tt= 23.876 s
get_depth_by_area                     tt= 22.135 s / 13.395 s
get_press_by_area                     tt= 19.943 s / 14.154 s
Apply_node_target_level_V4            tt= 18.726 s
_compute_general_hr_interface_flux    tt= 18.367 s
```

## 5. 按文件聚合的纯函数体耗时

`tottime` 聚合前几位：

```text
river_for_net.py                      1117.388 s
numpy/lib/_function_base_impl.py       195.103 s
numpy/lib/_type_check_impl.py           85.957 s
Rivernet.py                             52.510 s
networkx/classes/reportviews.py         42.312 s
xarray + pandas 相关                     数秒到十余秒
persistent_interpolator.py               4.385 s
```

结论：

- 主成本明显集中在 `river_for_net.py`。
- `Rivernet.py` 自身的纯函数体开销不高，但它调度出来的“内部节点边界更新”链路占据了非常大的累计时间。
- `xarray/pandas` 在整场 40h 运行中的纯开销很有限，不是主瓶颈。

## 6. 阶段级耗时判断

以下百分比基于 profile 总时长 `1921.656 s`，且为嵌套累计时间，只能用于“重要性排序”，不能直接相加：

```text
Update_boundary_conditions          50.46%
  Update_internal_boundary_conditions 47.07%
  Update_external_boundary_conditions_V2 3.38%

Caculate_Roe_flux_net              19.82%
Update_cell_property_net           12.60%
Assemble_flux_net                   7.90%
Check_Resample_and_Save...          3.71%
Save_step_result_net                1.62%
Caculate_global_CFL                 0.44%
```

这说明：

1. 当前最大的时间块在“边界更新，尤其是内部节点耦合”。
2. Roe 通量和单元状态回刷是第二梯队热点。
3. 运行中保存与最终重采样都不是主瓶颈。

## 7. 关键诊断结论

### 结论 1：当前不应把 I/O 当成首要优化目标

证据：

- `Save_step_result_net` 仅约 `1.62%`
- 最终 `Check_Resample_and_Save_Output_result` 仅约 `3.71%`
- 结果目录在长时间计算阶段几乎不增长，实际也符合 profile 结论

因此：

- 不能靠改输出频率获得核心提速
- 也没必要把第一轮精力放在 NetCDF 写盘上

### 结论 2：当前不应一上来就做河道级多进程

证据：

- `Update_internal_boundary_conditions()` 自身占到 `47.07%`
- 该阶段在每步里强依赖全网内部节点水位求解与统一施加
- 当前结构并不是“各河道先独立推进，再统一交换边界”

因此：

- 即便把 Roe 主链并行化，最多也只能覆盖部分耗时
- 如果不先压缩内部节点边界链和边界相关纯 Python 开销，多进程收益上限有限
- 过早并行化还会引入 `River` 大对象驻留、pickle、状态同步等额外复杂度

### 结论 3：存在一个非常有希望的低风险热点

`_append_stage_boundary_record()` 与相关诊断链在默认基线中占比异常高：

- `_append_stage_boundary_record` `ct=243.581 s`
- `_peek_interface_flux_for_diagnostics` `ct=198.988 s`
- `_append_stage_boundary_record` 每次都会构造完整记录并探测界面通量

但代码显示：

- `_append_boundary_diagnostics()` 一开始就判断 `if not self.enable_boundary_diagnostics: return`
- 默认情况下：
  - `enable_diagnostics = False`
  - `enable_boundary_diagnostics = False`

也就是说，当前 baseline 默认并不真正需要保存这批边界诊断，但仍然为此构造了大量记录与派生量。

这类优化若做成：

- “诊断关闭时，直接跳过 `_append_stage_boundary_record()` 的绝大多数构造”

则理论上属于：

- 不改数值原理
- 不改边界数学含义
- 不改默认对外输出文件
- 高概率带来明显提速

这是当前最优先的第一类低风险优化候选。

### 结论 4：大量断面查表 `np.interp` 是第二大成本簇

`np.interp` 相关累计非常高：

- `_function_base_impl.interp` `tt=173.831 s`
- `_multiarray_umath.interp` `tt=108.822 s`
- `get_width_by_area / get_depth_by_area / get_press_by_area / get_hydraulic_radius_by_area`
  的调用次数均在千万级

说明：

- 断面表查值是当前单河道核心成本之一
- 但这里直接优化需要非常谨慎，因为它深入数值链路
- 若后续动这里，必须先从“减少重复查询”和“缓存只读引用”做起，而不是贸然改算法

### 结论 5：`networkx`/动态调度有成本，但不是最大头

`call_river_function_by_name()` 本身 `tt=5.259 s`，但相关 `networkx reportviews` 聚合有约 `42.312 s`。

说明：

- 缓存河道对象列表、缓存内部/外部边界邻接关系，大概率能拿到一部分收益
- 但单靠这类调度瘦身，不足以把 `890 s` 压到接近 `60 s`

## 8. 初步优化判断

按当前证据，优化顺序应为：

1. 先做默认关闭诊断路径的真正短路
2. 再做 `Rivernet` 层的缓存与循环瘦身
3. 再评估边界查表与通量链中可安全减少的重复计算
4. 最后才决定是否值得做河道级并行

原因：

- 先动第 1 类，低风险、强热点、容易回归验证
- 第 2 类不改数学，侵入小
- 第 3 类最接近数值内核，需要更严格验证
- 第 4 类复杂度最高，且目前证据表明它并不是第一优先级

## 9. 本阶段结论

### 已确认

1. 当前 40h 原始串行基线的主瓶颈不是 I/O。
2. 主瓶颈首先是内部节点边界耦合及其边界状态恢复链。
3. 第二梯队瓶颈是 Roe 通量与状态回刷中的大量断面查表。
4. 立即上多进程不是当前最优第一步。
5. 默认关闭的边界诊断链存在明显低风险优化空间。

### 下一阶段行动

第 4 阶段将从最小侵入的第一类优化开始：

- 优先消除“默认关闭但仍大量构造”的边界诊断路径开销
- 每做一类优化就重新跑结果校验
- 若结果一致，再继续第二类优化

本阶段仍未修改求解逻辑。
