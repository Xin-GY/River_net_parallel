# Assemble_Flux_2 cpp plan

## target

在当前 continuation baseline 上，把 `Assemble_Flux_2` 里剩余的 Python per-cell post-step 链下沉到 C++ exact kernel：

- `_apply_explicit_friction_substep()`
- `_enforce_explicit_conservative_admissibility()`

不改：

- `_apply_explicit_conservative_increment()` 的 NumPy conservative update
- 任何边界语义
- `float64/float32` 参考语义
- dry / near-dry 判据

## exact constraints

- 只支持当前 accepted exact 的主命中路径：
  - `FRTIMP = True`
  - `friction_model == "manning"`
- 不支持的 friction mode 直接回退 Python
- 热路径里不再做：
  - section name 查找
  - table dict lookup
  - Python per-cell loop

## data reuse

复用 `CppUpdateCellPlan` 里的每 cell 断面表 view，不重新构 plan。

native kernel 输入：

- `S`
- `Q`
- `water_depth`
- `cell_s_limit`
- `_forced_dry_recorded`
- `g`
- `DT`
- `EPSILON`
- `water_depth_limit`
- `friction_min_depth`

## diagnosis strategy

这块最初的 C++ prototype 在 10m 上更快，但 exact compare 失败。

本轮修复顺序：

1. 先用单步对照脚本把首个分叉步压到最早时刻
2. 逐项定位 friction post-step 的数值语义
3. 修到 10m 全链 exact compare 通过后，再扩大到 2h / 40h

## expected gain

`Update_cell_proprity2` accepted 后，`Assemble_Flux_2` 是最清晰的剩余 per-cell native gap。

2h profiled before metric:

- `river_dispatch.Assemble_Flux_2.time = 3.056615 s`

因此它是当前 continuation 线最值得优先继续下沉的一块。
