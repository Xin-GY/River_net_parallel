# Caculate_Roe_matrix cpp implementation

## implementation split

新增 exact native kernel：

- C++:
  - `cpp/river_kernels.hpp`
  - `cpp/river_kernels.cpp`
- Cython wrapper:
  - `cython_river_kernels.pyx`
- Python routing:
  - `river_for_net.py`
- benchmark wiring:
  - `tools/profile_cpp_exact_serial.py`

feature flag:

- `ISLAM_CPP_USE_ROE_MATRIX=1`

## what moved to C++

`Caculate_Roe_matrix()` 现在在命中 feature flag 时，直接在 C++ 中完成：

1. `BETA_arr`
2. `Z / Lambda1 / Lambda2`
3. LeVeque 两个 mask 分支
4. `abs_Lambda1 / abs_Lambda2`
5. `alpha1 / alpha2`
6. `Vactor1 / Vactor2 / Vactor1_T / Vactor2_T`
7. `current_interface_counts`
8. `current_leveque_count`
9. `lambda_range_current`

Python fallback 保持原样，不删。

## exactness notes

这块的关键不在于复杂几何，而在于 dtype 语义。

当前 Python 参考实现里：

- `F_C/F_U/BETA/FR/U/C/S/Q` 主要是 `float32`
- `Vactor*` 和 `flag_LeVeque` 是 `float64`

因此 native kernel 的 exact 规则是：

- 中间主计算按 `float32` 进行
- 再把结果写入 `float64` 目标阵列

这样可以匹配 NumPy 参考路径的 dtype 传播，不会因为全部提升到 `double` 而引入微小漂移。

## validation status

当前 exact compare 结果：

- 10m: 通过
- 2h: 通过
- 40h: 通过

说明这块 kernel 可以进入 continuation line 的 accepted exact 配置。
