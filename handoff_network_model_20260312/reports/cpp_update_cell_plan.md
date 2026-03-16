# cpp update cell plan

## target

把 `River.Update_cell_proprity2()` 从当前 Python per-cell `_refresh_cell_state()` 主循环，下沉为 C++ exact kernel，同时保持：

- `float64` 几何/波速计算语义
- 当前数组更新顺序
- diagnostics 相关 bookkeeping 不丢
- feature flag 隔离

## why this is first

在当前 accepted phase-3 exact 配置下，`river_step.update_cell` 仍是明确的第一梯队 native gap：

- 2h corrected perf: `2.004452 s`
- 本质问题：
  - Python per-cell outer loop
  - near-dry / dry admissibility / geometry refresh 混在 Python 对象方法里
  - 每个 cell 都要走 table lookup 与状态写回

## design

1. 在 `cpp/river_kernels.cpp` 新增 `update_cell_properties_exact`。
2. 在 `cython_river_kernels.pyx` 新增：
   - `CppUpdateCellPlan`
   - `prepare_cpp_update_cell_plan(river)`
   - `update_cell_properties_exact_cpp(river)`
3. `CppUpdateCellPlan` 预绑定每个 cell 对应断面表的 raw array view：
   - `area -> level/depth/width/wetted/press`
   - `depth -> area`
   - `bed_level`
4. `River.Update_cell_proprity2()` 的顺序改为：
   - `ISLAM_CPP_USE_UPDATE_CELL=1` 时先尝试 C++ kernel
   - 失败再回退到现有 Cython exact kernel
   - 最后才回退到 Python loop

## exactness guard

- 不改公式
- 不改 dry / near-dry 判据
- 不改 counters 的累加时机
- 不改 fallback 行为
- 默认仍保持 `ISLAM_CPP_USE_UPDATE_CELL=0`

## exact-gap diagnosis

首轮 C++ candidate 与旧 Cython candidate 逐点一致，但它们都和 Python reference path 有同样的微小漂移。

根因最终定位为：

- 普通湿单元分支里，Python 原实现的
  - `U = float(Q) / self.S[idx]`
  - `C = np.sqrt(self.g * self.S[idx] / width)`
  - `FR = np.abs(self.U[idx]) / max(self.C[idx], self.EPSILON)`
- 实际走的是 `numpy.float32` 主导的舍入链
- 而旧的 Cython / C++ candidate 走的是：
  - `double` 计算
  - 末尾再 cast 到 `float32`

这会让 `C` 稳定差一个 float32 ULP，随后通过 CFL 与边界耦合逐步放大。

## promotion rule

修正 wet-cell `U/C/FR` 的 float32 舍入语义后：

- 10m compare: pass
- 2h compare: pass
- 40h compare: pass

因此当前这条 C++ kernel 已经满足升级为本分支 accepted exact 配置组成部分的条件。
