# evolve native gap topdown

当前 continuation 线已经把 `Update_cell_proprity2` 纳入 exact 工作基线。

关键对照：

- phase-3 accepted exact：
  - 40h `evolve/model = 202.210932 s`
- current continuation working baseline:
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - 2h `evolve/model = 9.865381956100464 s`
  - 历史 40h exact compare 已通过，40h `evolve/model = 177.525983 s`

这说明 `Update_cell_proprity2` 这一大块 native gap 已经被吃掉了。现在继续往下推时，bridge 本身更不是主瓶颈；真正的剩余成本已经集中到 nodechain 和 river-step 里还没有 native ownership 的链段。

## why the remaining gain is now harder

- `cython_cpp_bridge.run_cpp_network_evolve_serial()` 目前还是一个 Cython 壳，它每步依次调：
  - `Update_boundary_conditions`
  - `Caculate_face_U_C_net`
  - `Caculate_Roe_matrix_net`
  - `Caculate_Source_term_net`
  - `Caculate_Roe_flux_net`
  - `Assemble_flux_net`
  - `Update_cell_property_net`
  - `Caculate_global_CFL`
- 这些 `_net()` 入口大多只是 Python per-river dispatch，真正的 arrays/workspace 仍挂在 Python `River` 对象上。
- 因此 bridge 只省掉了最外层 generator/loop 的一部分解释器开销，没有真正消掉每步的 per-river/per-cell/per-interface Python 开销。
- 在 `Update_cell` native 化以后，bridge 的剩余问题更清楚了：
  - nodechain solve 之后的 state commit 仍有 Python ownership
  - `Assemble_Flux_2` 的 friction/admissibility 仍是 Python per-cell loop
  - `Roe matrix / face_uc / source` 仍通过 Python per-river dispatch 串联

## remaining native gaps

按预计收益排序：

1. nodechain state commit / final apply
   - wrapper-bypass 已绕开边界包装器，但 internal-node solve 的“算完 -> 写回 -> river-step 使用”还没有闭合在 native 层
   - 2h profiled metrics:
     - `boundary_updater.total = 9.075200 s`
     - `nodechain.total = 14.950724 s`
     - `nodechain.apply_and_boundary_closure = 6.499194 s`
     - `nodechain.final_apply = 0.618823 s`
   - 这里同时带着跨层对象协调和状态 write-back 开销

2. `Assemble_Flux_2`
   - 虽然 conservative increment 主要是 NumPy，但 friction substep 和 admissibility 仍是 Python per-cell loop
   - 2h profiled metric:
     - `river_dispatch.Assemble_Flux_2.time = 3.056615 s`
   - 这是当前最清晰的剩余 per-cell native gap

3. `Caculate_Roe_Flux_2`
   - 当前已有 Cython exact batch kernel，但 2h 里仍然是主热点之一：
     - `river_dispatch.Caculate_Roe_Flux_2.time = 3.825342 s`
   - 说明 general-HR 之外仍有一部分 river-step 协调/状态衔接留在 Python/Cython 边界上

4. `Caculate_Roe_matrix`
   - 主体是 NumPy，但仍通过 Python per-river dispatch 和 object state 访问
   - 2h profiled metric:
     - `river_dispatch.Caculate_Roe_matrix.time = 1.276841 s`

5. `Caculate_face_U_C`
   - 2h profiled metric:
     - `river_dispatch.Caculate_face_U_C.time = 0.712105 s`
   - 第二梯队，但仍是完整 fullstep native loop 的必要一环

6. `Caculate_source_term_2`
   - 2h profiled metric:
     - `river_dispatch.Caculate_source_term_2.time = 0.133709 s`
   - 当前不是第一优先级，但它仍阻断 fullstep native chain 的完整闭合

7. global CFL / dt reduction
   - 仍是 Python per-river reduction
   - 单步占比低于上面几项，但在 fullchain native loop 中值得顺手收走

8. output/state marshaling
   - bridge 已经把输出缓冲放进 C++
   - 剩余成本主要是 save 调度和跨层调用，不是当前 202s 级瓶颈

## execution order

1. `Assemble_Flux_2` 剩余 Python per-cell 子链
2. nodechain commit native 化
3. 根据重新 profile 后的顺序，在 `Roe_Flux / Roe_matrix / face_U_C` 中继续下沉下一块
4. fullstep native loop 合并
5. build flags / memory layout 微优化
