# Assemble_Flux_2 cpp implementation

## implementation split

新增 native exact post-step kernel：

- C++:
  - `cpp/river_kernels.hpp`
  - `cpp/river_kernels.cpp`
- Cython wrapper:
  - `cython_river_kernels.pyx`
- Python routing:
  - `river_for_net.py`

feature flag:

- `ISLAM_CPP_USE_ASSEMBLE=1`

默认仍关闭，只有在 exact compare 和 40h 收益都成立后才升级为推荐配置的一部分。

## what moved to C++

`Assemble_Flux_2()` 现在保持以下结构：

1. `_apply_explicit_conservative_increment()` 仍在 Python/NumPy
2. 若 `ISLAM_CPP_USE_ASSEMBLE=1` 且命中支持路径：
   - 调 `assemble_flux_poststep_exact_cpp(self)`
   - 完成 manning friction substep
   - 完成 post-step dry admissibility second pass
3. 否则回退原 Python：
   - `_apply_explicit_friction_substep()`
   - `_enforce_explicit_conservative_admissibility()`

## root cause of the original drift

首轮 native prototype 的问题不是高层调度，而是 friction post-step 里最基础的算术语义。

单步逐河道诊断表明：

- 最早分叉发生在 step 1
- 起点只是单个 cell 的 `Q` 差一个 float32 ULP
- 之后才累积到 `cfl_history` 和 `internal_node_history.csv`

真正的数值语义修复点有两处：

1. `coef` 的 Python reference 不是简单的 `double` 除法，也不是 `deb` 先压成 `float`
2. 正确链路是：
   - `g * DT * S` 先按 `numpy.float32` 口径收缩
   - `deb * deb` 先在 `double` 上计算
   - 再把平方结果按 `float32` 口径参与除法

也就是：

- 错误版本：
  - `coef = float(num2 / (deb_double * deb_double))`
  - 或 `coef = num2 / (deb_float * deb_float)`
- exact 版本：
  - `den = float(deb_double * deb_double)`
  - `coef = num2 / den`

修完这条链后，逐步诊断脚本在 10m 窗口内已经找不到任何分叉。

## implementation notes

- `TableView` 补了 `DEB_a` 指针，避免 friction 路径回 Python 取 `get_DEB_by_area`
- native kernel 只处理 interior cells：
  - `river.S[1:cell_num + 1]`
  - `river.Q[1:cell_num + 1]`
- `_forced_dry_recorded` 和 forced-dry counters 在 native kernel 内保持与 Python 同步
- unsupported friction modes 仍保留 Python fallback
