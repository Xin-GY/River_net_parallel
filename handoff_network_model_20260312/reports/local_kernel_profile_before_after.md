# Local Kernel Profile Before After

## Run Summary

| run | wall_time_s | model_time_s | step_count | process_files |
| --- | --- | --- | --- | --- |
| current_exact_parallel | 4.934541 | 2.08 | 181 | 1 |
| dea3202_ref_parallel | 5.013784 | 2.1 | 181 | 1 |
| current_exact_serial | 7.764195 | 4.94 | 181 | 1 |
| dea3202_ref_serial | 7.716107 | 4.9 | 181 | 1 |

## boundary_updater (default parallel exact)

| function | current_calls | ref_calls | current_time_s | ref_time_s | delta_time_s | current_per_call_ms | ref_per_call_ms | delta_per_call_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boundary_updater | 181 | 181 | 1.417245 | 1.426855 | -0.009610 | 7.830081 | 7.883177 | -0.053096 |

## Local River Kernels (serial isolation run)

| function | current_calls | ref_calls | current_time_s | ref_time_s | delta_time_s | current_per_call_ms | ref_per_call_ms | delta_per_call_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Caculate_face_U_C | 2534 | 2534 | 0.071641 | 0.073379 | -0.001738 | 0.028272 | 0.028958 | -0.000686 |
| Caculate_Roe_matrix | 2534 | 2534 | 0.129411 | 0.127928 | 0.001483 | 0.051070 | 0.050484 | 0.000585 |
| Caculate_Roe_Flux_2 | 2534 | 2534 | 0.815347 | 0.810225 | 0.005122 | 0.321763 | 0.319742 | 0.002021 |
| Assemble_Flux_2 | 2534 | 2534 | 0.419921 | 0.411801 | 0.008120 | 0.165715 | 0.162510 | 0.003204 |
| Update_cell_proprity2 | 2534 | 2534 | 0.537621 | 0.530737 | 0.006884 | 0.212163 | 0.209446 | 0.002717 |

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
