# Hotpath Diff vs dea3202

## Run Summary

| run | wall_time_s | model_time_s | step_count | process_files |
| --- | --- | --- | --- | --- |
| current_exact_parallel | 4.994964 | 2.1 | 181 | 1 |
| dea3202_ref_parallel | 5.109871 | 2.17 | 181 | 1 |
| current_exact_serial | 7.721540 | 4.87 | 181 | 1 |
| dea3202_ref_serial | 8.054557 | 4.91 | 181 | 1 |

## boundary_updater (default parallel exact)

| function | current_calls | ref_calls | current_time_s | ref_time_s | delta_time_s | current_per_call_ms | ref_per_call_ms | delta_per_call_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boundary_updater | 181 | 181 | 1.415279 | 1.451026 | -0.035746 | 7.819222 | 8.016716 | -0.197493 |

## Local River Kernels (serial isolation run)

| function | current_calls | ref_calls | current_time_s | ref_time_s | delta_time_s | current_per_call_ms | ref_per_call_ms | delta_per_call_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Caculate_face_U_C | 2534 | 2534 | 0.070925 | 0.075962 | -0.005038 | 0.027989 | 0.029977 | -0.001988 |
| Caculate_Roe_matrix | 2534 | 2534 | 0.127402 | 0.138064 | -0.010662 | 0.050277 | 0.054485 | -0.004208 |
| Caculate_Roe_Flux_2 | 2534 | 2534 | 0.813058 | 0.829148 | -0.016091 | 0.320859 | 0.327209 | -0.006350 |
| Assemble_Flux_2 | 2534 | 2534 | 0.415494 | 0.417479 | -0.001985 | 0.163968 | 0.164751 | -0.000783 |
| Update_cell_proprity2 | 2534 | 2534 | 0.533456 | 0.531704 | 0.001751 | 0.210519 | 0.209828 | 0.000691 |

## Code Diff Summary

- Current exact branch adds run-summary and dt-limiter profiling scaffolding around evolve/CFL bookkeeping.
- Current exact branch annotates river boundary roles during topology classification.
- No diff hunk lands inside the listed hot river kernels or the default parallel boundary updater path.
- parallel_river_pool.py is unchanged relative to dea3202.

## Notes

- `boundary_updater` is measured on the default exact parallel process backend with `fork`.
- Worker-side river kernels are isolated with a serial 10-minute run so the wrapper timing stays in-process and comparable across worktrees.
- Output paths are isolated under each worktree's `result/` tree; raw stdout/stderr logs are stored beside the JSON summaries.
- A positive `delta_*` means the current exact line is slower than raw `dea3202` on the same 10-minute case.
