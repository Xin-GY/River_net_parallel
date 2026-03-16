# cpp nodechain commit implementation

## implementation split

本次 exact pushdown 落在：

- `river_for_net.py`
- `cython_node_iteration.pyx`
- `Rivernet.py`
- `Islam.py`
- `tools/profile_cpp_exact_serial.py`

feature flag:

- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`

## what changed

### river-side prebound context

在 `river_for_net.py` 中新增：

- stage-boundary prebound signature/cache
- left/right prebound context builder
- side-specific exact commit helper
- `_stage_boundary_fix_level_cython_prebound_fast(side_code, level)`

这个 helper 直接复用当前 exact 的：

- `cython_compute_stage_boundary_mainline_fast`

但不再在每次 closure 调用时重复做：

- capability checks
- `side -> string`
- layout dict 构造
- tables dict repeated lookup
- `_commit_stage_boundary_state(ctx, ...)` 的 ctx dict 传递和动态 `setattr`

### nodechain loop routing

在 `cython_node_iteration.pyx` 中：

- 新增 `use_prebound_fast`
- 在 apply 阶段和 final apply 阶段优先命中：
  - `river._stage_boundary_fix_level_cython_prebound_fast(...)`
- 只有 prebound path 不可用时，才回退到原来的 direct-fast wrapper-bypass / Python wrapper

并新增统计：

- `nodechain.prebound_fast_hits`

## exactness notes

这一步不改公式，只改 fast-path 的 ownership：

- 仍然调用同一个 `cython_compute_stage_boundary_mainline_fast`
- 仍然按原 node/branch 顺序 apply
- 仍然按相同顺序更新 `S/Q`
- 仍然用相同 `level_hint` 调 `_refresh_cell_state`
- 仍然保持 `float64` `level` 和原有 CFL / dt 顺序

validation 结果：

- 10m: 通过
- 2h: 通过
- 40h: 通过

因此这块可以进入 continuation line 的 accepted exact 配置。
