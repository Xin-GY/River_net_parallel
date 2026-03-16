# C++ Kernelize-Next Hotspots Top 10

## Profiling Source

- run: 2-hour single-process exact profile after rebuilding `cython_cross_section`
- summary:
  - `cpp_kernelize_next_2h_cprofile_after_crosssection_summary.json`
  - `cpp_kernelize_next_2h_perf_after_crosssection_summary.json`
- raw Top 20:
  - `cpp_kernelize_next_2h_cprofile_after_crosssection_top20.json`
- perf counters:
  - `cpp_kernelize_next_2h_perf_after_crosssection.json`

## Raw Top 10 By Corrected 2h cProfile

| Rank | Function | Calls | Cumtime (s) | Notes |
| --- | --- | ---: | ---: | --- |
| 1 | `call_river_function_by_name` | 8892 | 12.789126 | Python river-phase dispatch wrapper |
| 2 | `Update_boundary_conditions` | 1482 | 9.506048 | total boundary updater shell |
| 3 | `Update_internal_boundary_conditions` | 1482 | 7.877429 | internal-node solve shell |
| 4 | `_try_update_internal_boundary_conditions_cython` | 1482 | 7.874596 | Cython nodechain entry, still Python-object heavy |
| 5 | `_stage_boundary_fix_level_cython_fast` | 337502 | 7.227246 | exact boundary-closure numeric kernel |
| 6 | `_refresh_cell_state` | 823598 | 5.977459 | repeated cell-state recompute in update path |
| 7 | `OutBound_Fix_level_V3` | 219895 | 4.862607 | Python wrapper around exact out-bound closure |
| 8 | `Caculate_Roe_Flux_2` | 20748 | 3.941565 | river-step flux kernel |
| 9 | `_commit_stage_boundary_state` | 337502 | 3.674813 | Python-side closure state writeback |
| 10 | `Update_cell_proprity2` | 20748 | 3.558095 | river-step update kernel |

## Corrected Perf Breakdown By Domain

Reference model time for the corrected 2h perf run:

- `12.060478 s`

Main measured components:

| Component | Time (s) | Share of evolve/model time |
| --- | ---: | ---: |
| `boundary_updater.total` | 4.076405 | 33.80% |
| `nodechain.apply_and_boundary_closure` | 2.771246 | 22.98% |
| `river_step.flux` | 2.312320 | 19.17% |
| `river_step.update_cell` | 2.004452 | 16.62% |
| `river_step.assemble` | 1.765988 | 14.64% |
| `river_step.roe_matrix` | 1.001271 | 8.30% |
| `boundary_updater.external` | 0.771885 | 6.40% |
| `river_step.face_uc` | 0.496444 | 4.12% |
| `nodechain.final_apply` | 0.261257 | 2.17% |
| `dt_update.global_cfl` | 0.190482 | 1.58% |
| `nodechain.residual_and_ac` | 0.156029 | 1.29% |
| `river_step.source` | 0.096717 | 0.80% |

## Boundary-Crossing Load

Corrected 2h perf counters show why the bridge itself only gave a tiny gain:

- steps: `1482`
- Python/Cython/C++ bridge crossings: `14820`
  - exactly `10` crossings per step
- nodechain iterations: `15319`
  - about `10.34` iterations per step
- boundary closure calls: `336020`
  - about `226.73` per step
- width lookup calls from nodechain residual/Ac assembly: `306380`
  - about `206.73` per step

So the current bridge still pays for:

1. one Python-orchestrated boundary updater per step
2. six Python river-phase dispatches per step
3. one save-step crossing per step
4. one CFL crossing per step
5. a nodechain path that still bounces through Python river methods and state commits hundreds of times per step

## Confirmed Top 3 Optimization Targets

Using the corrected single-process exact profile, the current Top 3 domains are:

1. `boundary_updater / internal node chain`
   - why it is hot:
     - dominant share of model time
     - hundreds of exact boundary-closure calls per step
     - Python wrapper cost remains around `_stage_boundary_fix_level_cython_fast`, `OutBound_Fix_level_V3`, and `_commit_stage_boundary_state`
     - nodechain is still only partially native
2. `Caculate_Roe_Flux_2`
   - why it is hot:
     - large per-face loop volume
     - still dispatched from Python once per step across all rivers
     - high cumulative cost even with existing Cython support
3. `Update_cell_proprity2`
   - why it is hot:
     - large per-cell update loop
     - repeated `_refresh_cell_state` work dominates the update side
     - still not deeply native in the current bridge line

`Assemble_Flux_2` remains the next target immediately behind the Top 3.

## What This Means

The bridge itself is no longer the main issue. The profile says the next real gains require:

1. moving the internal-node exact numeric chain deeper into native code
2. moving the Top 3 river-step outer loops into native kernels
3. collapsing the per-step Python dispatch fan-out so the time loop becomes a real native fullchain
