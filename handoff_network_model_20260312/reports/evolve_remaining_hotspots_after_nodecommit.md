# evolve remaining hotspots after nodechain prebound-fast commit pushdown

当前 accepted continuation exact 基线已更新为：

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

## headline change

这一步主要压掉的是 nodechain fast path 的 orchestrate/commit 壳：

- `boundary_updater.total`
  - `54.287393 s -> 48.312066 s`
- `nodechain.total`
  - `76.496979 s -> 64.568132 s`
- `nodechain.apply_and_boundary_closure`
  - `30.729300 s -> 25.667796 s`
- `nodechain.final_apply`
  - `5.202304 s -> 4.317332 s`

## current top remaining hotspots

1. `nodechain.total`
   - `64.568132 s`
   - 仍然是第一大 domain cost

2. `boundary_updater.total`
   - `48.312066 s`
   - nodechain 仍然主导这个域

3. `river_dispatch.Caculate_Roe_Flux_2.time`
   - `42.943128 s`
   - 当前最大的 river-step 单项热点

4. `river_dispatch.Assemble_Flux_2.time`
   - `5.897863 s`

5. `river_dispatch.Update_cell_proprity2.time`
   - `2.687484 s`

6. `river_dispatch.Caculate_source_term_2.time`
   - `1.768486 s`

7. `river_dispatch.Caculate_Roe_matrix.time`
   - `1.247942 s`

8. `river_dispatch.Caculate_face_U_C.time`
   - `0.538885 s`

## next top 3 to act on

下一批最值得继续 pushdown 的点已经更清晰了：

1. deeper `Caculate_Roe_Flux_2` ownership / C++ exact pushdown
2. nodechain residual/Ac 主体进一步 native 化
3. 然后再看 source tail 或 fullstep native loop

## practical recommendation

现在不要再回到 bridge/direct-dispatch 形态实验。

更有把握的顺序是：

1. 继续打 `Caculate_Roe_Flux_2`
2. 同时准备 nodechain residual/Ac 的更深 native 版本
3. 等这两块都吃掉之后，再考虑 fullstep native loop
