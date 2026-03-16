# C++ Nodechain Math And Dataflow

## Scope

This report describes the exact internal-node iteration used inside `Rivernet.Update_internal_boundary_conditions()` on the single-process exact path.

## Problem being solved

At each internal network node, the solver looks for a single node water level `eta` that makes branch-end flow satisfy mass balance:

- node residual:
  - `R(node) = sum(Q_in) - sum(Q_out)`
- exact target:
  - drive `R(node) -> 0`

The current default exact path does not use a surrogate table or predictor-only solve. It repeatedly applies a candidate node level to all incident branch ghost cells, recomputes branch-end discharge under the exact boundary closure semantics, then updates the node level with an Ac-based Newton-like increment.

## State categories

### Node-level state

- `node_levels[node]`
  - current candidate stage for the node
- `_internal_node_level_cache[node]`
  - last converged node stage used as next-step predictor
- `pure_Q`
  - mass residual at current node state
- `Ac`
  - effective sensitivity term used in `dR/dZ`

### River-side boundary state

For each incident branch, the node iteration updates one ghost-side boundary:

- incoming branch (`node` is downstream end)
  - right ghost cell / right boundary face
- outgoing branch (`node` is upstream end)
  - left ghost cell / left boundary face

The closure updates branch-side quantities such as:

- `S[ghost]`
- `Q[ghost]`
- `water_level[ghost]`
- `boundary_face_area_*`
- `boundary_face_width_*`
- `boundary_face_discharge_*`
- `boundary_face_level_*`

### Cell/face state read during node solve

- neighboring real-cell area / discharge:
  - incoming branch: `S[-2]`, `Q[-2]`
  - outgoing branch: `S[1]`, `Q[1]`
- ghost-cell state:
  - incoming branch: `S[-1]`, `Q[-1]`, `water_level[-1]`
  - outgoing branch: `S[0]`, `Q[0]`, `water_level[0]`

## Exact nodechain steps

### 1. Predictor initialization

For each internal node:

1. prefer `_internal_node_level_cache[node]` when enabled
2. else use average real-cell node level
3. else use average ghost-cell node level
4. else fall back to `0.0`
5. clamp to `>= 0`

This is orchestration plus node-level initialization. No branch state is mutated yet.

### 2. Apply candidate node level to all incident branches

For each iteration and for each node:

1. traverse incoming branches first
2. then traverse outgoing branches
3. for each branch call exact boundary closure:
   - incoming branch:
     - `OutBound_Fix_level_V2` or `OutBound_Fix_level_V3`
   - outgoing branch:
     - `InBound_Fix_level_V2` or `InBound_Fix_level_V3`

This is the core state mutation stage.

What it computes:

- given candidate node level `eta`, solve the branch-end exact stage boundary condition
- update ghost state and face state so downstream flux evaluation sees a consistent node boundary

What it mutates:

- ghost-cell area/discharge/water level
- boundary-face area/width/discharge/level
- possibly auxiliary closure diagnostics

### 3. Assemble node residual

After all incident branches of all nodes have had the candidate level applied:

For each node:

- incoming branch contributes positive discharge
- outgoing branch contributes negative discharge

Depending on flags, the residual may be read from:

- preferred boundary-face discharge
- averaged face/ghost discharge
- or direct ghost discharge

Current accepted exact default remains centered on ghost/boundary exact state, not a surrogate response table.

This stage is true numeric work, but today it still reads many Python attributes from river objects.

### 4. Assemble `Ac` or equivalent derivative approximation

For each node, `Ac` is formed from incident branch hydraulic state.

Three variants exist:

1. paper ghost-face Ac
2. V2 branch-regime-aware Ac
3. legacy ghost-cell Ac

Typical inputs per branch:

- `A`
- `B = width(A)`
- `Q`
- sometimes branch regime from neighboring real cell

The numerical role is:

- approximate `dR/dZ` through `-Ac`

This is true numeric work and one of the main geometry-query-heavy parts of the nodechain.

### 5. Newton-like level update

Per node:

- `dR_dZ = -Ac`
- `dz = -R / dR_dZ` when derivative is usable
- optional clip in non-paper mode
- apply relaxation factor
- update:
  - `eta_new = max(0, eta_old + dz)`

This stage is numerically simple; its cost is small compared with repeated exact branch closure and geometry lookup.

### 6. Convergence / stopping check

Stop when both are small enough:

- `max_abs_dz < 1e-4`
- `max_abs_q < JPWSPC_Q_limit`

Otherwise iterate again up to `max_iteration`.

### 7. Final synchronized apply

After convergence or reaching iteration limit:

- apply the final node levels one more time to all incident branches
- update `_internal_node_level_cache`

This guarantees subsequent river-step flux computation sees a boundary state consistent with the final node stage.

## What is orchestration vs numeric work

### Mostly orchestration

- predictor source precedence
- iterating over nodes and branch lists
- deciding whether V2 or V3 closure is used
- deciding which residual flavor and Ac flavor are active
- building history rows / diagnostics

### True numeric work

- exact branch-end boundary closure
- ghost/face discharge extraction
- width/area/chi/press/radius lookup from section tables
- Ac assembly
- residual assembly
- Newton-like update

## Current mutation ownership

### Mutated in place by nodechain

- river ghost states on all incident branches
- branch-end boundary-face scalars
- `_internal_node_level_cache`

### Read but not owned by nodechain

- real-cell hydraulic state adjacent to node
- section table geometry data
- global network time and output scheduler

## Why this chain is still not native enough

Even on the Cython path, the current exact nodechain still:

- stores branch plans as Python tuples of river objects
- calls Python methods for exact closure
- calls `cross_section_table.get_width_by_area(...)` through Python objects
- uses Python attribute access for face and ghost state

So the compiled shell exists, but the dominant branch-end numeric work is still not operating on native C++ arrays or native C++ table handles.

## Native C++ kernel target implied by this dataflow

To make the nodechain truly native, the kernel needs:

1. integer node ids and contiguous branch-offset arrays
2. integer river ids and side/sign codes
3. direct C++ access to:
   - ghost state arrays
   - adjacent real-cell state arrays
   - prebound section table handles
4. exact closure logic in C++, not Python method calls
5. residual and `Ac` accumulation in fixed serial order with `float64`

That is the point where the nodechain stops being “compiled orchestration” and becomes a real native numeric chain.
