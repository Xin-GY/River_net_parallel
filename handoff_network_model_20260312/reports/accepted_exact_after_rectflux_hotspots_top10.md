# Accepted Exact Fresh Hotspots After Rect Flux

Audit scope:

- branch: `feature/cpp-exact-accepted-reaudit-after-rectflux`
- base accepted checkpoint: `9a7c094`
- benchmark root: `/tmp/feature_cpp_exact_accepted_reaudit_after_rectflux`
- mode: single-process exact only
- accepted exact outputs reproduced exactly against
  `/tmp/feature_cpp_exact_accepted_reaudit_next`
  for 10m / 2h / 40h (`allclose = true`)

Fresh replay of the accepted exact path:

- 10m evolve/model time: `0.9353327751159668 s`
- 2h evolve/model time: `6.821141719818115 s`
- 40h evolve/model time: `63.882303953170776 s`
- 40h step count: `29783`

Notes:

- `Fine_cell_property2` and `Init_water_serface` still appear in perf stats because the
  perf registry spans more than the evolve headline window.
- They are excluded from blocker selection for this round because this task only optimizes
  `evolve/model time`.

## 40h Top 10

| Rank | Stage | Total time (s) | Share of evolve | Calls | Per-call | Layer | Ownership / remaining cost |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `nodechain.total` | 41.496887 | 64.96% | 59566 solves | 6.97e-4 / solve | Cython + Python | Aggregate bucket; most arithmetic is native, but part of the tail and surrounding orchestration still sits above native ownership |
| 2 | `boundary_updater.total` | 38.633809 | 60.48% | 29783 | 1.30e-3 | Python + Cython | Includes external boundary Python ownership and internal nodechain wrapper layer |
| 3 | `nodechain.apply_and_boundary_closure` | 16.989520 | 26.60% | 4010220 closure calls | 4.24e-6 | Cython + native helper | Deep apply already native-owned; remaining tail is much smaller than before |
| 4 | `boundary_updater.external` | 16.212713 | 25.38% | 29783 | 5.44e-4 | Python | Still heavy Python ownership: boundary dict lookup, lambda call, interpolator call, per-node dispatch |
| 5 | `river_step.assemble` | 6.566261 | 10.28% | 29783 | 2.20e-4 | Python + C++ helper | Native helper exists, but outer ownership and write-back remain in Python |
| 6 | `river_step.flux` | 4.360539 | 6.83% | 29783 | 1.46e-4 | Cython + C++ | Rectangular/general Roe flux are substantially native-owned now |
| 7 | `dt_update.global_cfl` | 3.936878 | 6.16% | 29783 | 1.32e-4 | Python | Per-river reduction loop and orchestration still in Python |
| 8 | `river_step.update_cell` | 3.405632 | 5.33% | 29783 | 1.14e-4 | Python + C++ helper | Helper exists, but ownership is not fully native |
| 9 | `nodechain.final_apply` | 2.803407 | 4.39% | 59566 solves | 4.71e-5 / solve | Cython + Python | Smaller than before; no longer first-order |
| 10 | `river_step.source` | 1.989544 | 3.11% | 29783 | 6.68e-5 | Python / NumPy | Still Python-owned but not the largest gap |

## 2h cProfile cross-check

The 2h profile is used to identify real function ownership inside the 40h buckets.

Key 2h cumulative costs:

- `Update_boundary_conditions`: `4.781 s`
- `Update_internal_boundary_conditions`: `2.935 s`
- `Update_external_boundary_conditions_V2`: `1.838 s`
- `InBound_In_Q2`: `1.180 s`
- `get_boundary_value`: `0.548 s`
- `PersistentLinearInterpolator.__call__`: `0.507 s`
- `q_boundary_value`: `0.468 s`
- `Assemble_Flux_2`: `0.462 s`
- `Caculate_Roe_Flux_2`: `0.344 s`
- `Update_cell_proprity2`: `0.222 s`

## Fresh Top 1 blocker candidate

After the rectangular Roe flux push, the strongest remaining first-order blocker with
clear Python ownership is no longer Roe flux. It is the external boundary update chain:

- `Update_external_boundary_conditions_V2`
- `get_boundary_value`
- Python lambdas in `Islam.apply_boundaries`
- `PersistentLinearInterpolator.__call__`
- per-node / per-river dispatch for `InBound_In_Q2` and `OutBound_*`
