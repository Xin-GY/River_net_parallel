# evolve remaining hotspots after Roe-matrix pushdown

当前 accepted continuation exact 基线已更新为：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

## headline change

`Caculate_Roe_matrix` 已经从第一梯队热点中明显退场：

- before:
  - `river_dispatch.Caculate_Roe_matrix.time = 19.322687 s`
- after:
  - `river_dispatch.Caculate_Roe_matrix.time = 1.342151 s`

## current top remaining hotspots

1. `boundary_updater.total`
   - `54.308294 s`
   - 主因：
     - nodechain orchestration
     - boundary closure
     - nodechain state commit / post-node write-back

2. `nodechain.total`
   - `76.469060 s` aggregate domain metric
   - 其中最重的是：
     - `nodechain.apply_and_boundary_closure = 30.683251 s`
     - `nodechain.final_apply = 5.217789 s`

3. `river_dispatch.Caculate_Roe_Flux_2.time`
   - `43.477875 s`
   - 当前仍是最大的 river-step 单项热点

4. `river_dispatch.Caculate_face_U_C.time`
   - `9.208925 s`

5. `river_dispatch.Assemble_Flux_2.time`
   - `5.699989 s`

6. `river_dispatch.Update_cell_proprity2.time`
   - `2.735255 s`

7. `river_dispatch.Caculate_source_term_2.time`
   - `1.813930 s`

## next top 3 to act on

在 `Update_cell_proprity2`、`Assemble_Flux_2`、`Caculate_Roe_matrix` 都 accepted 之后，下一批最值得继续 pushdown 的点是：

1. nodechain state commit / final apply native 化
2. deeper `Caculate_Roe_Flux_2` pushdown
3. `Caculate_face_U_C`

## practical recommendation

现在已经没有必要再回头做 bridge 形态或 dispatch 形态实验。

更有把握的顺序是：

1. native-ize nodechain 的算完后写回链
2. 若该链风险过高，则先收 `Caculate_face_U_C`
3. 之后再继续看 `Roe_Flux` 的更深 native ownership
