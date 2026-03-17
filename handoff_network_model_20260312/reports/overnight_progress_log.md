## 2026-03-16 phase 0/1 start

- 从 `feature/cpp-exact-evolve-kernelize-next@a67a12e` 新开 `feature/cpp-exact-evolve-fullchain-pushdown`。
- 保留旧工作树 `/tmp/feature_cpp_exact_evolve_kernelize_next` 作为 accepted phase-3 与历史实验的冻结副本。
- 记录了 source worktree 的 git status 和未跟踪中间产物；本轮明确不把这些编译/benchmark 产物混入 commit。
- 重新确认当前 accepted exact 配置与收益来源：
  - 真正 accepted 的收益来自 nodechain wrapper-bypass
  - direct-dispatch 继续保持 rejected 文档状态
- 输出了剩余 native gap 报告，结论是：
  - bridge 只有轻微收益，因为每步主链仍大量回调 Python `_net()` 包装器
  - 当前最值得优先 native 化的是 `Update_cell_proprity2`
  - `Assemble_Flux_2` 与 nodechain commit 是下一梯队

下一步：
- 直接实现 `Update_cell_proprity2` 的 C++ exact kernel
- 先做 10m / 2h compare 和阶段耗时对比，再决定是否推进 40h

## 2026-03-16 phase 2

- 新增了 `Update_cell_proprity2` 的 C++ exact-intent kernel：
  - `cpp/river_kernels.cpp`
  - `cython_river_kernels.pyx`
  - `river_for_net.py`
- 为了让 per-cell table view 能安全共享到 Cython/C++，补齐了：
  - `cython_cross_section.pxd`
  - `cython_cross_section.pyx` / `.pxd` 同步
- 第一轮 smoke 先撞到了 `CrossSectionTableCython` ABI mismatch，已修正。
- 正确的 10m absolute end time 已校正为 `2024-01-01 00:10:00`；之前用 `10:10:00` 跑成了 2h10m，已作废。
- 当前 `Update_cell_proprity2` C++ candidate 的事实结论：
  - 10m evolve/model: `1.457326 s -> 1.232814 s`
  - 步数保持 `181`
  - exact compare 未通过
  - 漂移签名与历史 Cython update-cell 实验一致：
    - `cfl_history time max_abs = 6.103515625e-05`
    - `internal_node_history.csv:n13_river14_face_Q max_abs = 0.0012717474781922533`
- 当前判断：
  - 这条 kernel 有明显性能潜力
  - 但还不能进入 accepted exact 配置
  - 下一步要么继续定位这条 kernel 的 exact gap，要么先去推进下一个可验证的 native gap

## 2026-03-16 phase 2 accepted fix

- 通过单步局部对照确认：
  - 新 C++ update-cell candidate 与旧 Cython candidate 逐点一致
  - 真正的 exact gap 根因不是 wrapper，而是普通湿单元分支里 `U/C/FR` 的舍入语义
- 具体修复：
  - 普通湿单元 `U/C/FR` 改为匹配 Python reference path 的 `numpy.float32` 运算链
  - near-dry branch 保持原 Python reference 的 double-style geometry chain
- 重新验证后：
  - 10m compare：通过
  - 2h compare：通过
  - 40h compare：通过
- 新的 accepted exact 结果：
  - 10m: `1.457326 s -> 1.259714 s`
  - 2h: `11.400661 s -> 10.262386 s`
  - 40h: `202.210932 s -> 177.525983 s`
- 当前判断：
  - `ISLAM_CPP_USE_UPDATE_CELL=1` 已可升级为本分支 accepted exact 配置组成部分
  - 这一轮收益主要来自把 `Update_cell_proprity2` 的 per-cell 主循环彻底 native 化

## 2026-03-16 phase 3 first attempt

- 开始推进 `Assemble_Flux_2` 的下一层 native pushdown：
  - 保留 NumPy `conservative increment`
  - 仅把 `manning/FRTIMP` 的 friction substep 和最终 dry-admissibility 做成 C++ exact-intent kernel
- 10m short run 速度很好：
  - `1.259714 s -> 1.099834 s`
- 但 10m exact compare 未通过：
  - 第一处分叉出现在 `time ~= 198.622894 s`
  - `cfl_history.csv` 首次出现 `1.5e-05` 量级时间偏差
  - `internal_node_history.csv` 随后出现 `1e-5 ~ 1e-3` 量级的流量漂移
- 额外定位结果：
  - step-1 单步局部对照是逐点一致的
  - 漂移是多步推进后才出现，不是首步立即分叉
- 当前判断：
  - 这条 `Assemble` kernel 还有性能潜力，但还不能进入 accepted exact 配置
  - 下一步应继续抓“首个分叉步”的局部 conservative/friction 状态差异，而不是直接推 2h/40h
