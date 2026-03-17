# Accepted Exact Fresh Hotspots Top 10

## Scope

- branch/worktree: `feature/cpp-exact-accepted-reaudit-next`
- start commit: `9535623`
- path under audit: accepted exact only
- config:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
  - `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
  - `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - `ISLAM_CPP_USE_ASSEMBLE=1`
  - `ISLAM_CPP_USE_ROE_MATRIX=1`
  - `ISLAM_CPP_USE_FACE_UC=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
  - `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`

## Measurement Note

The clean re-audit replay of `9535623` in this worktree measured:

- 10m: `1.233370 s`
- 2h: `9.695405 s`
- 40h: `101.177666 s`

The historical accepted checkpoint record on the source accepted branch is:

- 10m: `0.667691 s`
- 2h: `5.103571 s`
- 40h: `91.329929 s`

The absolute times drifted after rebuilding in a fresh worktree, but the blocker ordering stayed consistent with the accepted branch perf json. The ranking below uses the fresh re-audit 40h timer buckets and the 2h cProfile call-path drilldown.

## 40h Timer Buckets

Shares are relative to the fresh re-audit 40h `evolve/model time = 101.177666 s`. Timer buckets overlap; they are not exclusive.

| Rank | Bucket | 40h total (s) | Share | Calls | Main layer | Remaining ownership gap |
| --- | --- | ---: | ---: | --- | --- | --- |
| 1 | `river_step.flux` | 42.333267 | 41.8% | per-step river flux stage | Python + Cython + C++ | rectangular HR path still owned by Python per-face loop |
| 2 | `nodechain.total` | 38.318935 | 37.9% | 29783 step solves | Python + Cython | native helpers present, but orchestration ownership still mixed |
| 3 | `boundary_updater.total` | 36.705355 | 36.3% | 29783 | Python + Cython | includes nodechain and external BC shells |
| 4 | `nodechain.apply_and_boundary_closure` | 15.655460 | 15.5% | per-node iteration bucket | Cython-heavy | still mixed ownership on tail state handling |
| 5 | `river_step.assemble` | 7.132460 | 7.0% | river-step stage | Python wrapper + C++ kernel | native kernel exists, wrapper ownership remains |
| 6 | `river_step.update_cell` | 4.027083 | 4.0% | river-step stage | Python wrapper + C++ kernel | kernel native, surrounding refresh ownership still mixed |
| 7 | `dt_update.global_cfl` | 3.778728 | 3.7% | 29783 | Python/NumPy | reduction still Python-owned |
| 8 | `nodechain.final_apply` | 2.479389 | 2.5% | per-node iteration bucket | Cython + native cache | moderate tail cost remains |
| 9 | `river_step.source` | 1.911698 | 1.9% | river-step stage | Python/NumPy | still mostly Python-owned |
| 10 | `river_step.roe_matrix` | 1.684819 | 1.7% | river-step stage | Python wrapper + C++ kernel | mostly native math, wrapper ownership remains |

`river_step.face_uc = 0.808972 s` stayed below the Top 10 threshold for this round.

## 2h cProfile Drilldown

This is the call-path evidence that identifies the true blocker inside `river_step.flux`.

| Rank | Function | Cum. time (s) | Calls | Meaning |
| --- | --- | ---: | ---: | --- |
| 1 | `Rivernet.call_river_function_by_name` | 4.777736 | 8892 | Python dispatch shell around per-river stages |
| 2 | `Rivernet.Update_boundary_conditions` | 4.352165 | 1482 | step-level shell; overlaps nodechain |
| 3 | `Rivernet.Caculate_Roe_flux_net` | 3.735951 | 1482 | flux stage wrapper |
| 4 | `river_for_net.Caculate_Roe_Flux_2` | 3.706647 | 20748 | per-river flux entry |
| 5 | `river_for_net._caculate_roe_flux_rectangular_hr` | 3.408339 | 5928 | rectangular HR outer loop |
| 6 | `river_for_net._compute_rectangular_hr_interface_flux` | 3.170979 | 143754 | Python per-face ownership hotspot |
| 7 | `river_for_net._solve_rectangular_hr_roe_flux` | 1.731337 | 143754 | exact rectangular Roe solver under Python ownership |

## Fresh Audit Takeaway

The first-order blocker on the accepted exact path is not:

- refresh deep
- residual/Jacobian deep
- fullstep loop
- build-flag experiments
- dispatch reshaping

It is the remaining Python ownership inside the rectangular HR Roe-flux path.
