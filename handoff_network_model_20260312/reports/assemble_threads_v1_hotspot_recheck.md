# Assemble Threads V1 Hotspot Recheck

## Scope

This recheck was run on top of the latest accepted serial exact candidate:

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- commit: `445c2c9`
- configuration: accepted exact flags from that branch, including
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
  - `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`
  - `ISLAM_CPP_THREADS=0`

Fresh replay on this continuation worktree:

- 10m: `model_time_seconds = 0.422322`, `step_count = 181`
- 2h: `model_time_seconds = 6.124065`, `step_count = 1482`
- 40h: `model_time_seconds = 53.855951`, `step_count = 29783`

The fresh replay is slower than the historical accepted checkpoint record (`47.053824 s`), so this report uses the fresh replay only for **current hotspot ranking and feasibility**, not as a new acceptance gate.

## 40h Cost Recheck

Fresh 40h perf on the accepted serial exact path:

- `nodechain.total = 37.468292 s`
- `boundary_updater.total = 35.455287 s`
- `nodechain.apply_and_boundary_closure = 15.338548 s`
- `nodechain.final_apply = 2.462021 s`
- `river_step.update_cell = 3.282700 s`
- `river_step.assemble = 2.831578 s`
- `river_step.roe_matrix = 1.462046 s`
- `river_step.source = 1.318277 s`
- `river_step.face_uc = 0.798161 s`
- `dt_update.global_cfl = 0.708678 s`

Relative order outside the nodechain/boundary family is now:

1. `river_step.update_cell = 3.282700 s`
2. `river_step.assemble = 2.831578 s`
3. `river_step.roe_matrix = 1.462046 s`
4. `river_step.source = 1.318277 s`
5. `river_step.face_uc = 0.798161 s`
6. `dt_update.global_cfl = 0.708678 s`

## Assemble Threading Feasibility

### Ownership State

`Assemble_Flux_2` is now substantially native-owned:

- Python only routes the stage and feature flags
- Cython binds the arrays and launches the deep C++ kernel
- the C++ kernel owns:
  - conservative flux increment
  - exact Manning / friction post-step
  - conservative dry admissibility
  - stage-local write-back to `Flux`, `S`, `Q`

So from an ownership perspective, assemble is the cleanest threading candidate in the current accepted exact path.

### Disjoint Writes vs Shared Risk

Inside `rivernet::assemble_flux_exact_deep(...)`, each cell `i` only touches:

- `flux[2 * (i + 1)]`
- `flux[2 * (i + 1) + 1]`
- `S[i]`
- `Q[i]`
- `forced_dry_recorded[i]`

Read-only inputs are:

- `flux_loc`
- `flux_source_left/right/center`
- `flux_friction_left/right`
- `water_depth`
- `cell_s_limit`
- `cell_lengths`
- section table views

There is no global floating-point reduction in the deep assemble kernel itself. The only stage-local reduction-like value is `forced_dry_increment`, which can be handled with thread-local counters and a fixed-order serial merge.

### Grain Size Reality

The current accepted path calls the whole assemble stage once per global step:

- `river_step.assemble.calls = 29783`
- `river_step.assemble = 2.831578 s`
- average stage cost per step: about `9.51e-05 s` (`95 us`)

The river sizes are also small:

- total cells across the network: `293`
- largest river: `36` cells
- many rivers: `12` to `30` cells

This means the kernel is thread-friendly in shape, but **not** in grain size:

- per-river chunks are tiny
- even the full per-step assemble stage is only about `95 us`
- first-batch deterministic threading would spend a large fraction of that budget on worker wakeup, chunk coordination, and cache/synchronization overhead

## Why This Round Should Not Implement Assemble Threads

`Assemble_Flux_2` is still the most thread-friendly stage in the current accepted exact path, but it is **not** a high-confidence first threading implementation target under the current scope constraints.

Reasons:

1. `update_cell` is now slightly larger than assemble, but its deeper ownership space sits too close to the previously rejected refresh-deep family.
2. `nodechain / boundary_updater` still dominate raw time, but the obvious deeper routes there are still too close to the rejected refresh/fullstep/residual family.
3. `global_cfl` is already too small to justify threading.
4. assemble itself is now too fine-grained for per-river kernel threading to be credible:
   - max river only `36` cells
   - whole stage only `95 us` per step
5. The only plausible way to make assemble threading worthwhile would be a **coarser stage-level cross-river batching / persistent worker design**, which is outside this round's “deep assemble kernel only” guard and starts drifting toward orchestration-level changes.

## Verdict

Do **not** implement assemble threads in this round.

There is no higher-confidence replacement threads candidate within the allowed scope.

The unique conclusion for this branch is therefore:

- `assemble` remains the most thread-shaped stage
- but the current accepted baseline has already shrunk it below a credible first deterministic-threading target
- this round should stop at the feasibility audit instead of widening into implementation
