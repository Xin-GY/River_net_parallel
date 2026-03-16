# Caculate_face_U_C cpp plan

## target

在当前 accepted exact continuation 配置上，把 `Caculate_face_U_C()` 的整个 per-face 外层循环下沉到 C++ exact kernel。

这一步的目标不是改桥接形态，而是把当前仍在 Python 中逐界面执行的：

- `sqrt(max(S, limit))`
- `F_U` weighted average
- `F_C` 的 dry / near-dry / pressure ratio 分支

整体移入 native 层，减少：

- Python per-face loop
- NumPy 标量装箱/拆箱
- 每步重复的 `cell_limits`/`sqrt`/branch dispatch 开销

## baseline

当前 compare target 是 Roe-matrix accepted continuation baseline：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

在这个 baseline 上，`Caculate_face_U_C` 已经不是 Top 3 总热点，但仍然是：

- 一个每步必经的界面循环
- 当前最容易继续向 “fullchain native” 推进的一段 river-step 计算

## nativeization strategy

新增 exact kernel：

- C++:
  - `cpp/river_kernels.hpp`
  - `cpp/river_kernels.cpp`
- Cython wrapper:
  - `cython_river_kernels.pyx`
- Python routing:
  - `river_for_net.py`

feature flag:

- `ISLAM_CPP_USE_FACE_UC=1`

## exactness constraints

这块的 exact 风险主要来自 dtype 语义，而不是公式本身。

当前 Python 路径里：

- `S/U/C/PRESS/F_U/F_C` 是 `float32` arrays
- `cell_limits` 来自 `float64`

因此 native kernel 必须保持：

1. `limit_left/right` 用 `double`
2. `sqrt_left/right` 用 `double`
3. `fu` 与 `fc` 主计算用 `double`
4. 最终只在写回 `F_U/F_C` 时 cast 到 `float32`

不能把中间全过程都降成 `float32`，否则会把 `cell_limits` 的 `float64` 语义抹掉，长时段容易产生微小漂移。

## current expectation

如果 exact compare 通过，这个 kernel 应该成为 continuation line 的下一块 accepted exact 组件，并把推荐配置推进为：

- `ISLAM_CPP_USE_FACE_UC=1`

之后下一批更值得继续打的点会变成：

1. nodechain state commit / final apply native 化
2. deeper `Caculate_Roe_Flux_2` ownership
3. 然后再看 fullstep native loop
