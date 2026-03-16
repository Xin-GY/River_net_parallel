# evolve native gap topdown

accepted phase-3 exact 从 `206.306033 s` 降到 `202.210932 s`，收益只有 `4.095101 s`。这说明：

1. bridge 本身不是主要瓶颈；
2. wrapper-bypass 只解决了 nodechain 里一层明显的 Python 包装开销；
3. 绝大多数时间仍耗在“每步真实数值循环 + state write-back + Python/Cython 对象协调”。

## why bridge gain is small

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
- 因此 bridge 只省掉了最外层 generator/loop 的少量解释器开销，没有真正消掉每步的 per-river/per-cell/per-interface Python 开销。

## remaining native gaps

按预计收益排序：

1. `Update_cell_proprity2`
   - 仍是 Python per-cell `_refresh_cell_state()` 主循环
   - 包含 near-dry、width lookup、pressure/perimeter/radius 更新、forced-dry bookkeeping
   - 是当前最清晰的 native pushdown 目标

2. `Assemble_Flux_2`
   - 虽然 conservative increment 主要是 NumPy，但 friction substep 和 admissibility 仍是 Python per-cell loop
   - 与 update-cell 强相关，适合后续一起 native 化

3. nodechain state commit
   - wrapper-bypass 已绕开边界包装器
   - 但 internal-node solve 结束后的 state write-back、river-side 衔接仍未闭合在 native 层

4. `Caculate_source_term_2`
   - 仍是 Python per-interface loop
   - 伴随 `DEB`/friction/depth query 的 Python lookup

5. `Caculate_Roe_matrix`
   - 主体是 NumPy，但仍通过 Python per-river dispatch 和 object state 访问

6. `Caculate_face_U_C`
   - 与 Roe matrix 类似，内核矢量化已有，但 native fullstep 还没接上

7. global CFL / dt reduction
   - 仍是 Python per-river reduction
   - 单步占比低于上面几项，但在 fullchain native loop 中值得顺手收走

8. output/state marshaling
   - bridge 已经把输出缓冲放进 C++
   - 剩余成本主要是 save 调度和跨层调用，不是当前 202s 级瓶颈

## execution order

1. `Update_cell_proprity2` exact C++ kernel
2. `Assemble_Flux_2` 剩余 Python per-cell 子链
3. nodechain commit native 化
4. 当前 Top 3 中剩余的 river-step kernel
5. fullstep native loop 合并
6. build flags / memory layout 微优化
