# cpp nodechain apply/closure deep plan

## target

在 `d26ea2a` 的 accepted exact 配置上，继续把 nodechain 的
`apply_and_boundary_closure` 从“prebound fast helper + Python-owned refresh/face gather”
推进成更深的 native ownership。

本轮不改数学公式，不改迭代顺序，不改收敛逻辑，只处理：

- apply target level 的 exact 主数值链
- boundary closure 的 exact fast path ownership
- closure 后 face 状态缓存
- residual/Ac 所需的 width/face state 重复 lookup
- per-iteration 的 rebinding / object churn

## accepted baseline

baseline 配置：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`

40h baseline 指标：

- `evolve/model = 106.473473 s`
- `boundary_updater.total = 48.633332 s`
- `nodechain.total = 65.117052 s`
- `nodechain.apply_and_boundary_closure = 25.879760 s`
- `nodechain.residual_and_ac = 1.742821 s`
- `nodechain.final_apply = 4.360243 s`
- `nodechain.cython_to_python_boundary_calls = 4010220`
- `nodechain.cython_to_python_width_calls = 3414560`

## pushdown strategy

新增一个更深的 nodechain apply 路径：

- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`

设计要点：

1. 在 build plan 阶段预构建 `NodeBoundaryDeepPlan`
2. plan 内持有：
   - `river`
   - `side_code`
   - `ghost_idx / inner_idx / second_idx / dry_limit_idx`
   - `tbl_inner / tbl_target / tbl_second`
   - 常用 guard、`g`、`eps`、`water_depth_limit`、`dt_moc`
   - 直接映射到 river 状态数组的 typed memoryviews
3. 在 node iteration 内直接调用：
   - `compute_stage_boundary_mainline_fast(...)`
4. closure 成功后直接在 plan 内：
   - 写回 `S/Q`
   - 更新 cached face state
   - 为 implicit 向量更新 `V`
5. residual/Ac 路径优先复用 deep plan 的 face cache 和 direct width lookup

## exactness constraint

这一步不重写 ghost-cell refresh 的数值语义。初版全 native refresh 会导致漂移，
因此本轮 accepted 路径保留：

- left side: `river._refresh_cell_state(0, level_hint=level)`
- right side: `river._refresh_cell_state(-1, level_hint=level)`

这样做的含义是：

- closure / gather / width lookup ownership 已深推到 native 层
- ghost-cell refresh 仍沿用 Python 现有 exact 语义
- 先保证 10m / 2h / 40h strict compare 全通过，再继续往 refresh/commit 深处推进

## success criteria

本轮 accepted 条件：

1. 10m / 2h / 40h strict compare 全通过
2. `nodechain.apply_and_boundary_closure` 显著下降
3. `nodechain.total` 显著下降
4. 40h `evolve/model time` 明显优于 `106.473473 s`
