# cpp nodechain commit plan

## target

在当前 accepted continuation exact 配置上，继续压缩 internal-node exact chain 里的：

- direct-fast boundary closure 前的静态检查
- side/layout dict 构造
- `side` 字符串分支
- commit 阶段的动态 `setattr` / ctx dict 传递

这一步不改 node iteration 数学逻辑，不做近似，只把当前已经 100% 命中的 direct-fast path 改成更深的 prebound exact 路径。

## baseline

compare target 是当前 Face_U_C accepted continuation baseline：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

在这个 baseline 上，40h 里：

- `boundary_updater.total = 54.287393 s`
- `nodechain.total = 76.496979 s`
- `nodechain.apply_and_boundary_closure = 30.729300 s`
- `nodechain.final_apply = 5.202304 s`

说明真正还值得打的是 nodechain 内部已经“命中 fast path”的那条 exact closure + commit 链，而不是再去换 dispatch 形态。

## pushdown strategy

新增一个更深的 exact 路径：

- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`

设计点：

1. 对 left/right 两个 stage-boundary direct-fast closure 预构建 context
2. 预绑定：
   - `ghost_idx / inner_idx / second_idx / dry_limit_idx`
   - `tbl_inner / tbl_target / tbl_second`
   - `swap_moc_sign`
   - `guard thresholds`
3. 在 nodechain loop 内直接按 `side_code` 调用 prebound helper
4. commit 阶段直接走 side-specific exact write-back：
   - `S/Q`
   - `_refresh_cell_state`
   - `boundary_face_*`
   - implicit vectors

## expected gain

如果 exact compare 通过，主要收益应该直接落在：

- `nodechain.apply_and_boundary_closure`
- `nodechain.final_apply`
- `boundary_updater.total`

而不是 river-step kernels。
