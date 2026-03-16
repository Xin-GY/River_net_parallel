# evolve remaining hotspots after Face_U_C pushdown

当前 accepted continuation exact 基线已更新为：

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

## headline change

`Caculate_face_U_C` 已经从 river-step 剩余热点里明显退场：

- before:
  - `river_dispatch.Caculate_face_U_C.time = 9.305142 s`
- after:
  - `river_dispatch.Caculate_face_U_C.time = 0.590912 s`

## current top remaining hotspots

1. `boundary_updater.total`
   - `54.287393 s`
   - 主因：
     - nodechain orchestration
     - boundary closure
     - nodechain state commit / post-node write-back

2. `nodechain.total`
   - `76.496979 s`
   - 其中最重的是：
     - `nodechain.apply_and_boundary_closure = 30.729300 s`
     - `nodechain.final_apply = 5.202304 s`

3. `river_dispatch.Caculate_Roe_Flux_2.time`
   - `43.431397 s`
   - 当前仍是最大的 river-step 单项热点

4. `river_dispatch.Assemble_Flux_2.time`
   - `5.964801 s`

5. `river_dispatch.Update_cell_proprity2.time`
   - `2.678065 s`

6. `river_dispatch.Caculate_source_term_2.time`
   - `1.778863 s`

7. `river_dispatch.Caculate_Roe_matrix.time`
   - `1.246318 s`

8. `river_dispatch.Caculate_face_U_C.time`
   - `0.590912 s`

## next top 3 to act on

在 `Update_cell_proprity2`、`Assemble_Flux_2`、`Caculate_Roe_matrix`、`Caculate_face_U_C` 都 accepted 之后，下一批最值得继续 pushdown 的点是：

1. nodechain state commit / final apply native 化
2. deeper `Caculate_Roe_Flux_2` pushdown / ownership
3. 之后再看 source tail 或 fullstep native loop

## practical recommendation

现在已经更没有必要再回头做 dispatch 形态实验了。

更有把握的顺序是：

1. 把 nodechain 的算完后写回链继续 native-ize
2. 若 commit 链难度过高，再看 `Caculate_Roe_Flux_2` 是否还能做更深 ownership
3. 最后再考虑更完整的 fullstep native loop
