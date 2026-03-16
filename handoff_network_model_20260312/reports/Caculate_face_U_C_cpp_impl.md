# Caculate_face_U_C cpp implementation

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

- `ISLAM_CPP_USE_FACE_UC=1`

## what moved to C++

命中 feature flag 时，`Caculate_face_U_C()` 直接在 C++ 内完成整个界面循环：

1. `limit_left/right`
2. `sqrt_left/right`
3. `fu` weighted average
4. `fc` 的：
   - near-equal branch
   - pressure ratio branch
5. dry-state handling：
   - one-side-dry
   - both-dry
6. `F_U/F_C` 写回

Python fallback 保持原样，不删除。

## exactness notes

这里的关键不只是公式一致，而是中间 dtype 必须一致：

- `cell_s_limit` 用 `float64`
- `sqrt_left/right` 用 `double`
- `fu/fc` 用 `double`
- 最终只在写回 `F_U/F_C` 时转 `float`

这个选择是为了匹配 Python 参考路径里：

- `float32` 状态数组
- `float64` `cell_limits`
- NumPy 对混合 dtype 的传播顺序

## validation status

当前 compare 结果：

- 10m: 通过
- 2h: 通过
- 40h: 通过

所以这块 kernel 已经可以进入 continuation line 的 accepted exact 组合。
