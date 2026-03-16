# evolve remaining hotspots after assemble

工作基线已更新为：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

## headline change

`Assemble_Flux_2` 已经从第一梯队热点中退出：

- before:
  - `river_dispatch.Assemble_Flux_2.time = 3.056615 s`
- after:
  - `river_dispatch.Assemble_Flux_2.time = 0.300105 s`

这一步单独释放了约 `2.756510 s` 的 2h profiled time。

## current top remaining hotspots

1. `boundary_updater.total`
   - `3.896039 s`
   - 主因：
     - nodechain orchestration
     - boundary closure
     - nodechain state commit / post-node write-back

2. `nodechain.total`
   - `6.168860 s` aggregate domain metric
   - 其中最重的是：
     - `nodechain.apply_and_boundary_closure = 2.640967 s`
     - `nodechain.final_apply = 0.248829 s`

3. `river_dispatch.Caculate_Roe_Flux_2.time`
   - `2.212684 s`
   - 当前仍是主要 river-step gap

4. `river_dispatch.Caculate_Roe_matrix.time`
   - `0.962274 s`

5. `river_dispatch.Caculate_face_U_C.time`
   - `0.480100 s`

6. `river_dispatch.Update_cell_proprity2.time`
   - `0.155166 s`
   - 已不是主要 gap

7. `river_dispatch.Caculate_source_term_2.time`
   - `0.090593 s`

## next top 3 to act on

在 `Update_cell_proprity2` 和 `Assemble_Flux_2` 都 accepted 之后，下一批最值得继续 pushdown 的点变成：

1. nodechain state commit / final apply native 化
2. deeper `Caculate_Roe_Flux_2` pushdown
3. `Caculate_Roe_matrix` / `Caculate_face_U_C` 中更适合整体下沉的一块

## practical recommendation

现在不值得回头再做 bridge 形态实验。

更有把握的顺序是：

1. native-ize nodechain 的算完后写回链
2. 重新 profile 后，优先打 `Roe_Flux` 还是 `Roe_matrix`
3. 在这些真正的数值链都更 native 之后，再继续 fullstep native loop
