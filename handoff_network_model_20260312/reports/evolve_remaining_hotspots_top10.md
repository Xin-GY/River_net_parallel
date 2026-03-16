# evolve remaining hotspots top10

统计口径：当前 accepted phase-3 exact 配置，single-process，`evolve/model time` only。

依据：
- `reports/cpp_hotspots_top10.md`
- `reports/cpp_kernelize_next_2h_cprofile_after_crosssection_top20.json`
- `reports/cpp_kernelize_next_2h_perf_after_crosssection.json`

## top 10 summary

1. `boundary_updater.total`
   - 主因：nodechain orchestration + boundary closure + state write-back
   - 2h perf: `4.076405 s`
2. `nodechain.apply_and_boundary_closure`
   - 主因：大量 boundary closure 调用、node-level orchestration
   - 2h perf: `2.771246 s`
3. `river_step.flux`
   - 主因：Roe/general-HR flux 仍是 Python/Cython/C++ 混合层
   - 2h perf: `2.312320 s`
4. `river_step.update_cell`
   - 主因：Python per-cell state refresh / near-dry / geometry lookup
   - 2h perf: `2.004452 s`
5. `river_step.assemble`
   - 主因：friction/admissibility per-cell loop 仍在 Python
   - 2h perf: `1.765988 s`
6. `river_step.roe_matrix`
   - 主因：per-river dispatch + NumPy kernel 边界开销
   - 2h perf: `1.001271 s`
7. `river_step.source`
   - 主因：Python per-interface loop + lookup
8. `dt_update.global_cfl`
   - 主因：Python per-river reduction
9. `bridge.crossing.Save_step_result_net.time`
   - 主因：save 调度与 wrapper crossing
10. `bridge.crossing.Caculate_face_U_C_net.calls` 相关 crossing 聚类
   - 主因：每步重复 Python/Cython 边界往返

## top 3 to act on

本轮真正要打的 Top 3，按“剩余 native gap + 可整体下沉程度”排序：

1. `Update_cell_proprity2`
   - 类型：数值循环重 + Python object 开销重
   - 原因：整个 per-cell 外层循环仍在 Python，且含 near-dry / geometry / bookkeeping

2. `Assemble_Flux_2`
   - 类型：数值循环重 + Python per-cell loop
   - 原因：显式 friction/admissibility 子链未 native 化

3. nodechain state commit
   - 类型：边界 crossing 重 + Python 对象协调重
   - 原因：wrapper-bypass 后剩下的 write-back / post-node state 衔接仍没有 native ownership

## still important but not first

- `Caculate_Roe_Flux_2`
  - 已有可用 Cython exact kernel；除非阶段 2/3 后重新 profile 发现它再次成为主要 gap，否则本轮先不优先深挖
- `Caculate_Roe_matrix` / `Caculate_face_U_C` / `Caculate_source_term_2`
  - 属于第二梯队，按阶段 2 后的新 profile 决定先后
