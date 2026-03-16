# Caculate_Roe_matrix cpp plan

## target

在当前 accepted continuation baseline 上，把 `Caculate_Roe_matrix()` 的主外层接口循环整体下沉到 C++ exact kernel。

本轮不改：

- `Caculate_Roe_Flux_2` 现有 exact 路径
- 任何 LeVeque 逻辑判据
- 任何 dry / wet 语义
- 任何输出定义

只做：

- 原 `N = cell_num + 1` 的 per-interface 主循环 native 化
- 让 `Lambda` / `alpha` / `Vactor*` / `flag_LeVeque` 的核心计算留在 C++
- 保持 `float32` 中间量与 `float64` 存储阵列的现有语义

## why this one now

在 `Update_cell_proprity2` 和 `Assemble_Flux_2` 都 native 化后，40h 剩余热点排序里：

- `boundary_updater / nodechain` 仍是第一梯队
- `Caculate_Roe_Flux_2` 仍是最大 river-step 单项
- `Caculate_Roe_matrix` 已经变成最清晰、最干净的下一块 arrays-heavy native gap

当前 accepted assemble baseline 的 40h profiled metric：

- `river_dispatch.Caculate_Roe_matrix.time = 19.322687 s`

这说明它仍然值得单独收走。

## exact constraints

- 所有数值中间量保持 `float32` 口径，与 NumPy 在该链上的 dtype 传播一致
- `Vactor1/Vactor2/Vactor1_T/Vactor2_T` 仍写入 `float64` 数组，但写入值必须来自同一 `float32` 中间量
- 不允许：
  - `-ffast-math`
  - 重排 LeVeque 分支顺序
  - 改变 `flag_LeVeque` 的赋值优先级

## routing

新增 feature flag：

- `ISLAM_CPP_USE_ROE_MATRIX=1`

默认关闭，只有在：

- 10m compare 通过
- 2h compare 通过
- 40h compare 通过
- 40h `evolve/model time` 有净收益

后才纳入推荐 exact 配置。
