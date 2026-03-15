# Node Iteration Math And State

## What The Node Iteration Is Solving

At each global evolve step, the river network solves a nonlinear internal-junction compatibility problem:

- unknowns:
  - one water level `Z_node` per internal node
- objective:
  - make net inflow at each node vanish
- residual definition:
  - `R_node = sum(Q_in) - sum(Q_out)`
- update rule:
  - either decoupled scalar Newton-like updates per node
  - or a fully coupled numerical Jacobian solve when enabled

This is not the PDE interior update. It is the network coupling layer that sets branch-end ghost states before the river-local Roe/HR step.

## State Levels In The Model

### Node-level state

- `node_levels[node]`
  - current trial water level for an internal node
- `_internal_node_level_cache[node]`
  - previous converged node level reused as predictor

### River-end / ghost-cell state

Updated by `Apply_node_target_level_V4` and the river-side boundary closures:

- `river.S[0]`, `river.S[-1]`
- `river.Q[0]`, `river.Q[-1]`
- `river.water_level[0]`, `river.water_level[-1]`
- `river.water_depth[0]`, `river.water_depth[-1]`
- `river.U[0]`, `river.U[-1]`
- `river.C[0]`, `river.C[-1]`
- boundary-face mirrors:
  - `boundary_face_discharge_left/right`
  - `boundary_face_area_left/right`
  - `boundary_face_width_left/right`
  - `boundary_face_level_left/right`

### River real-cell / face / cell state

Read during node iteration, mainly from the first or last interior real cell:

- incoming branch uses `-2` / `-1` end
- outgoing branch uses `1` / `0` end

Important fields:

- `S`
- `Q`
- `water_level`
- `water_depth`
- `U`
- `C`
- `Flux_LOC` if face-flux residual mode is enabled

## Mathematical Meaning Of Each Step

### 1. Initial guess assembly

`Update_internal_boundary_conditions` seeds each node level from:

- previous converged node level, if cache is enabled
- otherwise average real-cell water level near the node
- fallback to ghost-cell average or zero

This is only a predictor. It does not mutate branch states yet.

### 2. Apply a trial node level to all incident branches

`_apply_internal_node_levels(node_levels)` loops over every internal node and calls `Apply_node_target_level_V4(node, level)`.

`Apply_node_target_level_V4` converts one node level into river-end boundary states:

- incoming branch:
  - node acts on the downstream ghost cell
  - boundary method: `OutBound_Fix_level_V3` or V2
- outgoing branch:
  - node acts on the upstream ghost cell
  - boundary method: `InBound_Fix_level_V3` or V2

If `Kj` were nonzero, the function would shift the effective boundary level by a local head-loss term. In the normal exact node solve, `Kj` stays at the default `0.0`.

### 3. River-side stage boundary closure

Each branch-end closure solves an exact stage boundary problem:

- input:
  - target stage
  - adjacent interior state
  - section geometry / hydraulic tables
  - current boundary-control flags
- output:
  - boundary area `Ab`
  - boundary discharge `Qb`
  - derived boundary width / depth / celerity / face state

In the accepted baseline, the internal-node route already hits `_stage_boundary_fix_level_cython_fast` when the runtime flags allow it, which means the low-level characteristic closure formula is already Cythonized. The remaining cost is largely the repeated Python orchestration around it.

### 4. Residual evaluation

After all node trial levels have been applied, the network computes each node residual:

- default:
  - ghost discharge balance from `Get_node_clear_flow_at_ghost_cell_net`
- optional diagnostic mode:
  - interface flux balance from `Get_node_clear_flow_at_boundary_face_net`

This produces `R_node = Qin - Qout`.

### 5. Jacobian or denominator evaluation

Two modes exist.

#### Default decoupled Newton-like mode

For each node:

- compute denominator `dR/dZ` approximately using one of:
  - `Caculate_node_Ac_at_ghost_cell_JPWSPC`
  - `Caculate_node_Ac_at_ghost_cell_V2`
  - `Caculate_node_Ac_at_ghost_cell`
- update:
  - `dz = -R / dR_dZ`
  - optional clipping in non-paper mode
  - relaxation: `dz = relax * dz`

#### Numeric Jacobian modes

If enabled, the code perturbs node level(s), reapplies branch-end boundary states, recomputes residuals, and builds a finite-difference derivative or full Jacobian.

This is exact in semantics but very expensive because it re-enters the whole apply/residual chain.

### 6. Convergence / stopping

The iteration stops when both are small enough:

- maximum level correction
- maximum mass residual

Then the final converged node levels are applied one more time so the subsequent river-local PDE step uses a consistent set of ghost states.

## Which Functions Mutate State In Place

### Orchestration + mutation

- `Update_internal_boundary_conditions`
- `_apply_internal_node_levels`
- `Apply_node_target_level_V4`

### True numeric mutation at river side

- `InBound_Fix_level_V3`
- `OutBound_Fix_level_V3`
- `_commit_stage_boundary_state`
- `_refresh_cell_state`
- `_set_boundary_face_state`

These update `S`, `Q`, `water_level`, `water_depth`, `U`, `C`, `FR`, `PRESS`, `R`, and the boundary-face mirror fields.

### Read-only helpers in the node solve

- `Get_node_clear_flow_at_ghost_cell_net`
- `Get_node_clear_flow_at_boundary_face_net`
- `Caculate_node_Ac_at_ghost_cell*`
- `Caculate_node_average_level_at_real_cell`
- `Caculate_node_average_level_at_ghost_cell`

These mostly read the already-updated branch-end states.

## Orchestration vs Real Computation

### Mostly orchestration

- `Update_internal_boundary_conditions`
- `_apply_internal_node_levels`
- `_internal_residual_vector`
- `_internal_jacobian_numeric`
- `Apply_node_target_level_V4`

These functions mostly:

- build Python dicts
- loop over nodes and branches
- dispatch method calls
- decide which closure or residual helper to call

### Real hydraulic computation

- `_stage_boundary_fix_level_cython_fast`
- Python stage-boundary fallback helpers
- `_commit_stage_boundary_state`
- `_refresh_cell_state`
- `Caculate_node_Ac_at_ghost_cell*`

These compute actual hydraulic quantities from area, width, stage, discharge, and celerity.

## Implication For Cythonization

The single-process Cython target is not to change the exact formulas. It is to remove repeated Python orchestration around already exact formulas by:

- precompiling the node-to-branch traversal
- replacing `dict[str, float]` node state maps with dense arrays
- replacing repeated network-level method dispatch with tight Cython loops
- preserving the same branch order, node order, update order, and accumulation order
