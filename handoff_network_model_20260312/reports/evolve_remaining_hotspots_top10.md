# evolve remaining hotspots top10

统计口径：当前 continuation working baseline，single-process，`evolve/model time` only。

工作基线：

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

依据：

- no-profile headline:
  - `reports/cpp_fullchain_pushdown_next_updatecell_10m_summary.json`
  - `reports/cpp_fullchain_pushdown_next_updatecell_2h_noprof_summary.json`
- hotspot ordering:
  - `reports/cpp_fullchain_pushdown_next_updatecell_2h_perf.json`
  - `reports/cpp_fullchain_pushdown_next_updatecell_2h.prof`

说明：

- 2h no-profile `evolve/model = 9.865382 s`
- profiler 会抬高绝对 wall，但不改变当前剩余热点排序，因此下面的模块时间使用 profiled metrics 只作排序与 native-gap 判断，不直接当作 headline 速度。

## top 10 summary

1. `nodechain.total`
   - 主因：internal-node solve 仍有大量 Python-owned state read/write 和 closure orchestration
   - 2h profiled metric: `14.950724 s`
2. `boundary_updater.total`
   - 主因：nodechain 外围 orchestration + boundary closure + state write-back
   - 2h profiled metric: `9.075200 s`
3. `nodechain.apply_and_boundary_closure`
   - 主因：大量 boundary closure 调用、node-level orchestration
   - 2h profiled metric: `6.499194 s`
4. `river_step.flux`
   - 主因：Roe/general-HR flux 仍是 Python/Cython/C++ 混合层
   - 2h profiled metric: `3.825342 s`
5. `river_step.assemble`
   - 主因：friction/admissibility per-cell loop 仍在 Python
   - 2h profiled metric: `3.056615 s`
6. `river_step.roe_matrix`
   - 主因：per-river dispatch + NumPy kernel 边界开销
   - 2h profiled metric: `1.276841 s`
7. `nodechain.final_apply`
   - 主因：node iteration 算完后的 write-back 和 post-node state commit
   - 2h profiled metric: `0.618823 s`
8. `river_step.face_uc`
   - 主因：per-river dispatch + native chain still open
   - 2h profiled metric: `0.712105 s`
9. `river_step.update_cell`
   - 主因：已 native 化，剩余只剩 wrapper/fallback/router 成分
   - 2h profiled metric: `0.227052 s`
10. `river_step.source`
   - 主因：Python per-interface loop + lookup
   - 2h profiled metric: `0.133709 s`

## top 3 to act on

本轮真正要打的 Top 3，按“剩余 native gap + 可整体下沉程度”排序：

1. `Assemble_Flux_2`
   - 类型：数值循环重 + Python per-cell loop
   - 原因：显式 friction/admissibility 子链未 native 化

2. nodechain state commit
   - 类型：边界 crossing 重 + Python 对象协调重
   - 原因：wrapper-bypass 后剩下的 write-back / post-node state 衔接仍没有 native ownership

3. `Caculate_Roe_Flux_2`
   - 类型：数值循环重 + mixed-layer orchestration
   - 原因：已有 Cython batch，但仍是当前 river-step 最大单项热点之一

## still important but not first

- `Caculate_Roe_matrix` / `Caculate_face_U_C`
  - 属于第二梯队，按 `Assemble` 和 nodechain commit 之后的新排序决定先后
- `Update_cell_proprity2`
  - 已经从“主 gap”降到“已 native 化、只剩少量 wrapper 成分”
