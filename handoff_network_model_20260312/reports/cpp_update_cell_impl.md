# cpp update cell implementation

## touched pieces

- `cpp/river_kernels.hpp`
- `cpp/river_kernels.cpp`
- `cython_cross_section.pxd`
- `cython_cross_section.pyx`
- `cython_river_kernels.pyx`
- `build_cython_exact_kernels.py`
- `river_for_net.py`

## what moved to C++

`Update_cell_proprity2()` 的 per-cell 主循环已经有一个新的 C++ exact-intent kernel：

1. clamp `S`
2. `area -> level/depth`
3. dry 判据
4. near-dry / wet-cell 的 `U/C/Fr`
5. `P/PRESS/R`
6. `QIN=0`
7. forced-dry counter increment

## prebinding model

`CppUpdateCellPlan` 在 Cython 层预构建一次 per-cell `TableView`：

- raw axis pointers
- wet-width axis pointers
- bed level
- axis lengths

这样 C++ kernel 不再需要在热路径中做：

- `section name -> table` 查找
- Python dict lookup
- Python object method dispatch

## feature flag wiring

- runtime flag:
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
- caller:
  - `River.Update_cell_proprity2()`
- fallback chain:
  - C++ kernel
  - existing Cython exact kernel
  - Python `_refresh_cell_state()` loop

## build changes

`cython_river_kernels` 现在按 C++ extension 构建，并链接：

- `cpp/river_kernels.cpp`

同时补齐了 `cython_cross_section.pxd/.pyx` 的定义同步，避免后续 kernel 扩展时再次出现 ABI mismatch。

## current status

实现已可运行，并且在修正 wet-cell `U/C/FR` 的舍入语义后，当前状态为：

- 10m exact compare: pass
- 2h exact compare: pass
- 40h exact compare: pass
- 40h evolve/model:
  - `202.210932 s -> 177.525983 s`

## exactness fix that mattered

旧的 native candidate 复现了历史 Cython update-cell 的 exact gap，问题不在 table view 或 wrapper，而在普通湿单元分支的数值表达式：

- Python reference path uses `numpy.float32`-dominated arithmetic for wet-cell `U/C/FR`
- old native paths used `double -> cast float32`

当前 C++ kernel 已改为：

- wet-cell `U`: float32 division
- wet-cell `C`: float32 sqrt chain
- `FR`: based on already-written float32 `U/C`

near-dry branch仍保留原 Python reference 的 double-style geometry chain。
