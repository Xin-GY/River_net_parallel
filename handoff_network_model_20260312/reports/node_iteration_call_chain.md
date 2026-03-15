# Node Iteration Call Chain

## Entry Path

1. `Islam.py`
   - builds `net = Rivernet(top, model_data)`
   - configures runtime flags with `configure_net_options(net, ...)`
   - initializes per-river settings with `initialize_rivers(net)`
   - runs `for t in net.Evolve(1800): ...`
2. `Rivernet.Evolve(yield_step)`
   - initializes river states and save schedule
   - enters `_evolve_base` style main loop
   - each step calls `Update_boundary_conditions()`
3. `Rivernet.Update_boundary_conditions()`
   - `Update_external_boundary_conditions_V2()`
   - `Update_internal_boundary_conditions()`

The internal-node solve lives entirely under `Update_internal_boundary_conditions()` in the serial exact path.

## Internal-Node Solve Chain

### Outer step loop

- Caller: `Rivernet.Evolve`
- Callee: `Rivernet.Update_boundary_conditions`
- Frequency: once per global evolve step
- Loop level: global time-step loop
- Hot path: yes

### Boundary split

- Caller: `Update_boundary_conditions`
- Callee:
  - `Update_external_boundary_conditions_V2`
  - `Update_internal_boundary_conditions`
- Frequency: once per global step
- Loop level: global time-step loop
- Hot path: `Update_internal_boundary_conditions` yes, external BC usually lower cost

## `Update_internal_boundary_conditions()`

### Stage 1: initial node level guess assembly

- Inputs:
  - `self.internal_nodes`
  - `self._internal_node_level_cache`
  - `Caculate_node_average_level_at_real_cell`
  - `Caculate_node_average_level_at_ghost_cell`
- Output:
  - `node_levels: dict[str, float]`
- Frequency:
  - once per global step before node iterations
- Hot path:
  - warm but not dominant versus per-iteration closure work

### Stage 2A: coupled Newton branch

- Guard:
  - `self.internal_use_coupled_newton`
- Iteration loop:
  - `for iter_time in range(1, self.max_iteration + 1)`
- Per-iteration callees:
  - `_internal_residual_vector(node_levels)`
    - calls `_apply_internal_node_levels(node_levels)`
    - then `_get_node_mass_residual_current_state(n)` for each node
  - `_internal_jacobian_numeric(node_levels, residual_vec)`
    - repeated calls to `_internal_residual_vector(plus_map)`
    - each call again triggers `_apply_internal_node_levels`
  - linear solve:
    - `np.linalg.solve` or `np.linalg.lstsq`
  - stopping check on `max_abs_dz` and `max_abs_q`
- Frequency:
  - once per internal-node iteration
- Loop nesting:
  - global step -> internal-node iteration -> Jacobian columns -> node residual vector -> per-node branch application
- Hot path:
  - yes

### Stage 2B: decoupled / JPWSPC-style branch

- Guard:
  - default exact path when `internal_use_coupled_newton == False`
- Iteration loop:
  - `for iter_time in range(1, self.max_iteration + 1)`
- Per-iteration flow:
  1. `_apply_internal_node_levels(node_levels)`
  2. for each node:
     - `_get_node_mass_residual_current_state(n)`
  3. for each node:
     - if numeric Jacobian:
       - `_node_mass_jacobian_numeric_with_map(n, node_levels, pure_Q)`
       - this calls `_apply_internal_node_levels(level_map_plus)`
       - then `_get_node_mass_residual_current_state(n)`
       - then `_apply_internal_node_levels(node_levels)` to restore
     - else analytic denominator:
       - `Caculate_node_Ac_at_ghost_cell_JPWSPC`
       - or `Caculate_node_Ac_at_ghost_cell_V2`
       - or `Caculate_node_Ac_at_ghost_cell`
  4. level update and stopping check
- Frequency:
  - once per internal-node iteration
- Loop nesting:
  - global step -> internal-node iteration -> all nodes -> optional per-node numeric Jacobian
- Hot path:
  - yes, this is the main serial internal-node hot chain

## `_apply_internal_node_levels(node_levels)`

- Caller:
  - `Update_internal_boundary_conditions`
  - `_internal_residual_vector`
  - `_node_mass_jacobian_numeric_with_map`
  - `_internal_jacobian_numeric`
- Callee:
  - `Apply_node_target_level_V4(n, node_levels[n])` for every internal node
  - optionally `_synchronize_internal_branch_end_discharge()`
  - optionally `_update_boundary_flux_for_current_state()`
- Frequency:
  - multiple times per internal iteration
- Loop level:
  - node-iteration inner loop
- Hot path:
  - yes

## `Apply_node_target_level_V4(node_name, level, Kj=0.0, regime='sub')`

- Caller:
  - `_apply_internal_node_levels`
  - `_node_mass_residual`
- Callee:
  - for incoming branches:
    - `river.OutBound_Fix_level_V3(...)` or `river.OutBound_Fix_level_V2(...)`
  - for outgoing branches:
    - `river.InBound_Fix_level_V3(...)` or `river.InBound_Fix_level_V2(...)`
- Frequency:
  - once per internal node per application pass
- Loop level:
  - node application loop inside node-iteration loop
- Hot path:
  - yes

## River-side exact boundary closure path

### `River.InBound_Fix_level_V3(level, ...)`

- Caller:
  - `Apply_node_target_level_V4` for outgoing branches
- Internal flow:
  1. try `_stage_boundary_fix_level_cython_fast('left', ...)`
  2. else Python fallback:
     - `_prepare_stage_boundary_context`
     - `_prepare_stage_boundary_target_state`
     - `_classify_stage_boundary_entry`
     - `_resolve_stage_boundary_chi_bundle`
     - `_compute_stage_boundary_characteristic_velocity_with_explicit_chi`
     - `_apply_stage_boundary_stabilizers`
     - `_commit_stage_boundary_state`
     - `_append_stage_boundary_record`
- Frequency:
  - once per outgoing incident branch for each node-level application
- Hot path:
  - yes

### `River.OutBound_Fix_level_V3(level, ...)`

- Caller:
  - `Apply_node_target_level_V4` for incoming branches
- Same structure as inbound but acting on the right boundary
- Frequency:
  - once per incoming incident branch for each node-level application
- Hot path:
  - yes

## Residual evaluation

### `_get_node_mass_residual_current_state(node)`

- Caller:
  - `Update_internal_boundary_conditions`
  - `_node_mass_residual`
  - `_internal_residual_vector`
  - `_node_mass_jacobian_numeric_with_map`
- Branches:
  - `Get_node_clear_flow_at_boundary_face_net(node)` if face-flux residual mode is enabled
  - else `Get_node_clear_flow_at_ghost_cell_net(node)` by default
- Frequency:
  - once per node per residual evaluation
- Hot path:
  - yes

### `Get_node_clear_flow_at_ghost_cell_net(node)`

- Caller:
  - `_get_node_mass_residual_current_state`
- Work:
  - sums incoming ghost discharges
  - subtracts outgoing ghost discharges
  - optionally uses boundary-face discharge or ghost/cell averaged discharge
- Frequency:
  - per residual evaluation
- Hot path:
  - yes, but lighter than closure

## Jacobian / denominator assembly

### Analytic denominator

- `Caculate_node_Ac_at_ghost_cell`
- `Caculate_node_Ac_at_ghost_cell_V2`
- `Caculate_node_Ac_at_ghost_cell_JPWSPC`

Caller:
- `Update_internal_boundary_conditions`

Frequency:
- per node per iteration in the default decoupled branch

Hot path:
- yes, moderate

### Numeric Jacobian helpers

- `_node_mass_jacobian_numeric`
- `_node_mass_jacobian_numeric_with_map`
- `_internal_jacobian_numeric`

These are much more expensive because they recursively re-enter `_apply_internal_node_levels`.

## Stopping checks

- Location:
  - inside `Update_internal_boundary_conditions`
- Metrics:
  - `max_abs_dz < 1e-4`
  - `max_abs_q < self.JPWSPC_Q_limit`
- Frequency:
  - once per internal-node iteration
- Hot path:
  - orchestration only, negligible compared with closure calls

## Hot-Path Summary

### True numeric hot chain

`Rivernet.Evolve`
-> `Update_boundary_conditions`
-> `Update_internal_boundary_conditions`
-> `_apply_internal_node_levels`
-> `Apply_node_target_level_V4`
-> `River.InBound_Fix_level_V3` / `River.OutBound_Fix_level_V3`
-> `_stage_boundary_fix_level_cython_fast` or Python boundary closure helpers
-> `_get_node_mass_residual_current_state`
-> `Caculate_node_Ac_at_ghost_cell*`
-> stopping check

### Orchestration-heavy nodes

- repeated Python `dict[str, float]` construction for `node_levels`, `new_levels`, `node_residual`
- repeated per-node branch loops over `_in_branches_by_node` / `_out_branches_by_node`
- repeated Python method dispatch from network -> river -> closure helper
- optional recursive application passes for numeric Jacobian
