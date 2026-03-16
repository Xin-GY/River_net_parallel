# evolve remaining hotspots after update-cell

统计口径：

- current branch: `feature/cpp-exact-evolve-fullchain-pushdown`
- exact config:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- profiling source:
  - `reports/cpp_fullchain_pushdown_updatecell_2h_perf.json`

## headline change

`Update_cell_proprity2` 已不再是第一梯队热点：

- before:
  - `river_dispatch.Update_cell_proprity2.time = 1.997687 s`
- after:
  - `river_dispatch.Update_cell_proprity2.time = 0.215858 s`

这一步单独释放了约 `1.781829 s` 的 2h evolve 时间。

## current top remaining hotspots

1. `boundary_updater.total`
   - `4.039533 s`
   - 主因：
     - nodechain orchestration
     - boundary closure
     - nodechain state commit / post-node write-back

2. `nodechain.total`
   - `6.368011 s` aggregate domain metric
   - 其中最重的是：
     - `nodechain.apply_and_boundary_closure = 2.722140 s`
     - `nodechain.final_apply = 0.256200 s`

3. `river_dispatch.Caculate_Roe_Flux_2.time`
   - `2.324625 s`
   - 说明当前 Cython Roe batch 虽然已有效，但仍是主要 river-step gap

4. `river_dispatch.Assemble_Flux_2.time`
   - `1.756987 s`
   - 仍有 conservative/friction/admissibility per-cell 子链未 native 化

5. `river_dispatch.Caculate_Roe_matrix.time`
   - `1.015139 s`
   - 仍以 Python per-river dispatch + NumPy kernel 为主

6. `river_dispatch.Caculate_face_U_C.time`
   - `0.510132 s`
   - 第二梯队

7. `river_dispatch.Caculate_source_term_2.time`
   - `0.093936 s`
   - 当前不是第一优先级

## next top 3 to act on

在 `Update_cell_proprity2` accepted 之后，下一批最值得继续 pushdown 的点变成：

1. nodechain state commit / final apply native 化
2. `Assemble_Flux_2`
3. deeper `Caculate_Roe_Flux_2` or `Caculate_Roe_matrix`

## practical recommendation

短期内不要再回头改 bridge 形态。

更有把握的顺序是：

1. native-ize nodechain 的算完后写回链
2. native-ize `Assemble_Flux_2` 中剩余 per-cell Python 子链
3. 重新 profile，再决定先打 Roe matrix 还是继续深挖 Roe flux
