# Source Deep V1 Hotspot Recheck

## Scope

This recheck treats `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2@445c2c9` as the authoritative accepted exact baseline.

The `main` branch index is stale and was not used as the starting point.

## Evidence Used

Two evidence sources were combined for this phase-1 decision:

1. The accepted branch's own 40h stage-level perf record at `445c2c9`, which remains the authoritative accepted exact stage breakdown for this code path.
2. A fresh local 2h accepted-config cProfile/perf replay on this continuation worktree to attribute current Python ownership inside the source stage.

The local runner disabled only the final netCDF write call via a no-op monkeypatch because this machine currently lacks a working `h5netcdf` install. That patch does not alter the accepted numerical path, time stepping, history recording, or stage execution order.

## Current 40h Cost Ranking On The Accepted Exact Path

Current accepted 40h stage costs from the `445c2c9` branch-local accepted reports:

- `nodechain.total = 34.057932 s`
- `boundary_updater.total = 32.375613 s`
- `river_step.update_cell = 2.673096 s`
- `river_step.assemble = 2.428812 s`
- `river_step.source = 1.244976 s`

Interpretation:

- Raw Top 1 is still `boundary_updater / nodechain`.
- `source` is smaller than `update_cell` and `assemble`.
- But `assemble` is already accepted on this baseline, and `boundary_updater` has just produced an exact no-go on same-harness 40h A/B.

## Fresh 2h Ownership Recheck

Fresh local 2h replay on the accepted exact path:

- `model_time_seconds = 67.646056 s`
- `step_count = 1482`

Relevant perf counters from this 2h replay:

- `boundary_updater.total = 38.408555 s`
- `boundary_updater.external = 2.000059 s`
- `nodechain.total = 36.164007 s`
- `river_dispatch.Update_cell_proprity2.time = 7.833614 s`
- `river_dispatch.Assemble_Flux_2.time = 5.437486 s`
- `river_dispatch.Caculate_source_term_2.time = 0.087662 s`

Relevant cProfile attribution:

- `Rivernet.call_river_function_by_name`: `cumtime = 25.964420 s`
- `Rivernet.Caculate_Source_term_net`: `cumtime = 0.093040 s`
- `river_for_net.Caculate_source_term_2`: `cumtime = 0.078348 s`
- `river_for_net.get_DEB_by_area`: `cumtime = 0.889822 s`, `ncalls = 434226`

The important detail is that source-stage Python cost is not dominated by the wrapper itself. The visible ownership gap is:

- Python per-interface loop in `Caculate_source_term_2`
- Python cross-section table dispatch through `cross_section_table.get_DEB_by_area(section_name, area)`
- repeated per-interface left/right section lookup by string key
- Python branching for:
  - Manning/off switch
  - minimum-depth bypass
  - small `sd-sg` interpolation path
  - denominator clip / friction-clip counting

## Current Ownership Boundary In `Caculate_source_term_2`

At `445c2c9`, `Caculate_source_term_2` remains almost entirely Python-owned:

- the outer interface loop is Python
- left/right section selection is Python via `self.cell_sections[i]` / `self.cell_sections[i + 1]`
- table lookup is Python via `cross_section_table.get_DEB_by_area(...)`
- friction/source assembly is Python
- writes to `self.friction_source[i, :]` are Python

What is already native-owned elsewhere on the accepted path:

- `Update_cell_proprity2`
- Roe flux deep ownership
- rectangular Roe flux deep ownership
- assemble deep ownership
- Roe matrix
- face-UC
- global CFL reduction

What is **not** yet covered by an accepted native path:

- source-stage per-interface DEB lookup + friction/source assembly

## Why This Round Should Still Target Source

### Why not boundary shell

`boundary_shell_v1` already narrowed this family:

- shell-only deepening is exact
- same-harness 40h A/B shows no net gain
- grouped evaluator batching is not exact at 40h

So this family is currently a no-go for exact-only continuation.

### Why not assemble threads

`assemble_threads_v1` already concluded:

- shape is thread-friendly
- grain size is too small
- not worth first deterministic C++ thread implementation

That path is paused by explicit no-go evidence.

### Why not nodechain deeper families

The remaining obvious nodechain routes are still too close to already-rejected:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping

This round should not reopen those families.

### Why not update_cell first

`update_cell` is numerically larger than `source`, but its remaining ownership is much closer to the cell-state / refresh territory that has already produced rejected exact continuations.

By contrast, `source` is:

- smaller, but still material at `1.244976 s` over 40h
- still almost fully Python-owned
- structurally isolated from the rejected boundary/nodechain families
- implementable with a clean left/right section-table plan and a serial native kernel

That makes `source` the highest-confidence next move **outside** the already-rejected families, even though it is not the largest raw non-nodechain stage.

## Unique Decision

`source-term` remains the single continuation target for this round.

No parallel candidate is retained.

## Phase-1 Verdict

Proceed to `Caculate_source_term_2` serial exact deeper ownership pushdown.
