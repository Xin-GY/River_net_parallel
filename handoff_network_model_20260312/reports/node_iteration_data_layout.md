# Node Iteration Data Layout

## Current Hot-Path Structures

### Network-side graph and branch maps

- `self.G`
  - NetworkX DiGraph, setup-time topology holder
- `_in_branches_by_node[node]`
  - list of `(river_obj, river_name)` tuples
- `_out_branches_by_node[node]`
  - list of `(river_obj, river_name)` tuples
- `_river_edges`
  - list of `(u, v, data)` for all rivers

### Node iteration dynamic containers

- `node_levels: dict[str, float]`
- `new_levels: dict[str, float]`
- `node_residual: dict[str, float]`
- `level_map_plus = dict(node_levels)`
- `plus_map = dict(node_levels)`

These are rebuilt inside hot loops and are prime candidates for replacement by dense `float64` arrays plus integer-indexed node order.

### River-side state arrays

These are already contiguous NumPy arrays and are good Cython inputs:

- `S`
- `Q`
- `water_level`
- `water_depth`
- `U`
- `C`
- `PRESS`
- `R`
- `cell_lengths`

### River-side section identity / table references

Useful existing prebindings in `river_for_net.py`:

- `_section_name_to_id`
- `_section_table_refs_by_id`
- `_section_id_by_cell`
- `_cell_section_tables`
- `_general_hr_left_tables`
- `_general_hr_right_tables`

These show the codebase already has the right direction: integer ids and prebound table refs instead of repeated string lookup. The nodechain can reuse the same idea for boundary cells.

## Confirmed Python Object Costs In The Node Chain

### 1. Dict lookup by node name

Examples:

- `node_levels[n]`
- `_internal_node_level_cache[n]`
- `node_residual[n]`
- `new_levels[n]`

Why it hurts:

- string-key lookup inside iteration loops
- repeated full-dict copies for Jacobian perturbations

Best replacement:

- fixed node ordering array
- `levels[i]`, `residuals[i]`, `dz[i]`
- contiguous `float64` arrays or memoryviews

### 2. Incident branch lookup by node name

Examples:

- `_in_branches_by_node[node]`
- `_out_branches_by_node[node]`

Why it hurts:

- repeated dict lookup
- repeated iteration over Python tuples

Best replacement:

- precompiled node-branch plan
- `node_offsets[i]:node_offsets[i+1]`
- arrays:
  - `branch_river_index`
  - `branch_side_code`
  - `branch_flow_sign`

### 3. Small tuple/list object churn

Examples:

- `(river_temp, name)` tuples in branch maps
- temporary `level_list` and `river_name` in average-level helpers
- `level_map_plus = dict(node_levels)`
- `plus_map = dict(node_levels)`

Best replacement:

- contiguous arrays for level sums and counts
- no list construction during hot iteration

### 4. Method dispatch layers

Examples:

- network -> river:
  - `Apply_node_target_level_V4` -> `InBound_Fix_level_V3` / `OutBound_Fix_level_V3`
- river -> helper:
  - `_stage_boundary_fix_level_cython_fast`
  - `_commit_stage_boundary_state`

The branch-end closure itself already has a Cython fast path, but the traversal, bookkeeping, and repeated Python dispatch still dominate the serial node chain.

### 5. Section-name and table lookups

Still visible in boundary closure helpers:

- `self.cell_sections[idx]`
- `self.cross_section_table.tables.get(sec_name)`
- `self.cross_section_table.get_width_by_area(sec_name, area)`
- `self.cross_section_table.get_area_by_level(sec_name, level)`

For the nodechain path specifically, boundary cells only touch:

- left ghost / left inner / optional left second
- right ghost / right inner / optional right second

Best replacement:

- prebind per-branch boundary table refs:
  - target table
  - inner table
  - second table if needed
- pass them into Cython once, not looked up by section name each iteration

## Structures Best Suited For Cython Typed Views

### Node-plan arrays

- `node_offsets[int32]`
- `node_branch_start[int32]` or same via offsets
- `node_branch_count[int32]`
- `node_levels[float64]`
- `node_residual[float64]`
- `node_dz[float64]`

### Branch-plan arrays

- `branch_river_slot[int32]`
- `branch_side_code[int8]`
- `branch_flow_sign[int8]`
- `branch_node_index[int32]`

### River-boundary scalar arrays

For direct exact nodechain Cython calls, prebind and cache Python object arrays once, then pass typed scalars each iteration:

- inner/ghost indices
- `g`
- flags controlling V2/V3 closure branch
- maybe arrays of Python objects for:
  - `river` instances
  - `CrossSectionTableCython` table refs

If full elimination of Python-object calls is not feasible in one pass, the first Cython version should still move:

- node iteration loops
- residual assembly loops
- Ac loops
- stopping logic

while keeping a narrow Python callback boundary for the exact branch-end closure.

## Most Promising Exact Cythonization Boundaries

### Best first target: node orchestration shell

Move into Cython:

- node-level arrays
- node loop
- per-iteration residual loop
- Ac loop
- stopping loop

Keep Python callback initially for:

- exact river-side boundary apply

This already removes the most obvious `dict[str, float]` and small-object churn.

### Best second target: branch-end apply traversal

Move into Cython:

- iteration over precompiled incident branches
- side-code-based dispatch
- fixed-order residual accumulation

Potential boundary:

- a Cython helper receives precompiled branch plan and invokes exact left/right closure callbacks in fixed order

### Best third target: residual and Ac batch assembly

These use only already-updated river-end states and are easy to convert to dense array accumulation once branch order is fixed.

## Data Layout Conclusion

The serial nodechain is currently bottlenecked less by raw math and more by:

- Python dicts keyed by node name
- Python lists/tuples for incident branches
- repeated dynamic dispatch across network and river objects
- repeated string-based table lookup at branch ends

The right exact Cython strategy is therefore:

1. integerize node/branch traversal
2. prebind boundary table refs
3. move the outer node-iteration loops into Cython
4. keep float64 and exact accumulation order unchanged
