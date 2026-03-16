# evolve remaining python chain

当前 pushdown continuation 的工作基线：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

说明：

- phase-3 对照基线仍然是 `ISLAM_CPP_USE_UPDATE_CELL=0` 的 accepted exact 路径。
- 但当前这条 continuation 分支已经把 `Update_cell_proprity2` native kernel 接纳为新的工作基线，因为后续剩余 native gap 必须以这条更强的 exact 路径来排序。
- 当前 clean worktree 复核结果：
  - 10m `evolve/model`: `1.2669095993041992 s`
  - 2h `evolve/model`: `9.865381956100464 s`
  - 与 phase-3 exact 对照相比，步数保持不变，收益来自单步成本下降。

## real entry chain

1. `Islam.prepare_net_for_evolve()`
   - Python
   - 做 case/runtime 准备，不计入本轮 headline 时间
2. `Islam.run_prepared_evolve()`
   - Python
   - 进入 `Rivernet._run_prepared_evolve()`
3. `Rivernet._run_prepared_evolve()`
   - Python
   - 当 `ISLAM_USE_CPP_EVOLVE=1` 时调 `cython_cpp_bridge.run_cpp_network_evolve_serial()`
4. `cython_cpp_bridge.run_cpp_network_evolve_serial()`
   - Cython
   - 这是当前 bridge 主循环，但每个时间步仍逐段回调 Python `net.*_net()` 包装器

## one-step stage breakdown

### A. `Update_boundary_conditions`
- 入口层：Cython -> Python
- 主执行层：Python
- 子链：
  - `Update_external_boundary_conditions_V2()`：Python，逐节点/逐分支调 Python river boundary 方法
  - `Update_internal_boundary_conditions()`：Python 主控；优先尝试 `run_internal_node_iteration_exact()`（Cython）
  - `run_internal_node_iteration_exact()` 内部仍频繁回 Python river 对象：
    - stage-boundary fast path 已经命中 Cython direct-fast
    - 但 node-level commit、残差配套状态读取、部分 width/state 口径仍依赖 Python object/attribute
- hot-path：是
- remaining gap：
  - Python node/branch orchestration 仍存在
  - state commit 和后续 river-step 衔接仍未 native 完整闭合

### B. `Caculate_face_U_C_net`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river dispatch；river 内主体是 NumPy 向量化
- 仍存在：
  - Python per-river 循环
  - Python/Cython 边界 crossing
- hot-path：中等

### C. `Caculate_Roe_matrix_net`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river dispatch；river 内主体是 NumPy 向量化
- 仍存在：
  - Python per-river dispatch
  - Python object attribute 访问
- hot-path：中等偏高

### D. `Caculate_Source_term_net`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river dispatch + Python for-loop
- 仍存在：
  - Python per-interface loop
  - `DEB` / depth / friction 路径的 Python lookup
- hot-path：中等

### E. `Caculate_Roe_flux_net`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river dispatch；river 内 general-HR 显式路径已下沉到 Cython batch
- 仍存在：
  - Python per-river dispatch
  - 仍有非 batch 辅助状态和 source/positivity 协调留在 Python/Cython 混合层
- hot-path：高，但已有一部分 native 化

### F. `Assemble_flux_net`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river dispatch
- river 内：
  - `_apply_explicit_conservative_increment()` 主要是 NumPy
  - `_apply_explicit_friction_substep()` 仍是 Python per-cell loop
  - `_enforce_explicit_conservative_admissibility()` 仍是 Python per-cell loop
- hot-path：高
- remaining gap：
  - 显式 conservative 更新链只 native 了 `Update_cell` 之后的部分前提条件
  - 真正的 friction/admissibility post-step 仍在 Python per-cell loop

### G. `Update_cell_property_net`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river dispatch
- river 内：
  - 当前 continuation 基线已经命中 C++ `update_cell_properties_exact`
  - Python 层仍保留：
    - per-river dispatch
    - feature-flag / fallback 路由
    - forced-dry 计数与 diagnostics 相关的轻量衔接
- hot-path：已明显下降
- remaining gap：
  - 仍有少量 wrapper/fallback 成分，但不再是当前最值得优先 pushdown 的主 gap

### H. `Caculate_global_CFL`
- 入口层：Cython -> Python wrapper
- 主执行层：Python per-river loop
- 仍存在：
  - Python reduction
  - per-river `Caculate_CFL_time_for_river_net()` object dispatch
- hot-path：中等

### I. output path
- `Save_step_result_net()` / `_finalize_evolve_outputs()`
- bridge 已把输出缓冲持久化到 C++
- 但 save 调度和 river 数据提取仍经 Python wrapper
- 因本轮 headline 只看 evolve/model time，这部分只在 crossing 统计中记录，不作为初始化优化对象

## why the bridge still does not dominate the gain

- 2h profiled run里仍有：
  - `336020` 次 nodechain boundary-closure 调用
  - `306380` 次 width lookup
  - `14820` 次 bridge step-level Python crossing
- 这说明目前的主要成本已经不再是“有没有 C++ bridge”，而是：
  - nodechain 结束后的 native ownership 还不够完整
  - `Assemble_Flux_2` 的 per-cell post-step 仍留在 Python
  - `Roe/Matrix/Face_U_C` 仍有明显的 per-river Python dispatch 和跨层衔接
