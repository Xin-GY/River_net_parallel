# nodechain tail remaining python chain

## accepted exact context

This report is for the accepted exact continuation path on commit `f8f0db0` with:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

## real call chain

### 1. evolve entry

- Python: `Islam.run_prepared_evolve(...)`
- Python: `Rivernet._run_prepared_evolve(...)`
- Cython/Python bridge: `cython_cpp_bridge.run_cpp_network_evolve_serial(...)`

At this point the step loop is still owned by the bridge, but the nodechain itself can route into the Cython exact path.

### 2. boundary updater entry

- Cython bridge calls Python: `net.Update_boundary_conditions()`
- Python: `Rivernet.Update_boundary_conditions()`
- Python: `Rivernet.Update_external_boundary_conditions_V2()`
- Python: `Rivernet.Update_internal_boundary_conditions()`

### 3. internal node exact entry

- Python: `Rivernet.Update_internal_boundary_conditions()`
- Python/Cython boundary: `Rivernet._try_update_internal_boundary_conditions_cython()`
- Cython: `cython_node_iteration.run_internal_node_iteration_exact(...)`

This is the current native nodechain entry.

## per-iteration chain

### A. predict

- Cython:
  - build `levels[i]` from `net._internal_node_level_cache`
  - fallback to Python averages only if cache misses

Current ownership:

- main loop: Cython
- cache lookup object: Python dict

### B. apply_and_boundary_closure

- Cython outer loops over nodes and incident branches
- Cython deep plan path:
  - `NodeBoundaryDeepPlan.apply_level(level)`
  - direct `compute_stage_boundary_mainline_fast(...)`
  - direct `S/Q` write to typed arrays

Current remaining Python ownership inside deep path:

- `NodeBoundaryDeepPlan._refresh_committed_state(...)`
  - calls `river._refresh_cell_state(...)`

This is the main remaining Python-owned tail in the hot path.

Current status:

- no Python dict-of-dict
- no string side dispatch in hot loop
- no Python boundary helper calls
- no Python width lookups
- but still one Python method call per successful closure

### C. residual / Ac

- Cython outer loops
- Cython consumes:
  - cached face level/area/Q/width from deep plan
  - direct table width lookup from prebound table refs

Current Python ownership:

- effectively removed from the hot path for the accepted exact route

### D. update and stopping

- Cython:
  - Newton-like `dz` update
  - relax
  - stopping checks

Current Python ownership:

- none in the accepted hot path

### E. final_apply

- Cython outer loops over nodes and branches again
- deep plan path again uses:
  - `NodeBoundaryDeepPlan.apply_level(...)`

Current remaining Python ownership in final apply:

- same `river._refresh_cell_state(...)` call inside `_refresh_committed_state(...)`
- then Cython calls:
  - `NodeBoundaryDeepPlan.sync_python_boundary_state()`

That sync writes Python-side attrs:

- `boundary_face_level_left/right`
- `boundary_face_area_left/right`
- `boundary_face_discharge_left/right`
- `boundary_face_width_left/right`

This means final apply is not yet full native ownership. The cached face state is native, but the authoritative exposed boundary-face attrs are still synchronized back to Python object fields branch by branch.

### F. state commit / write-back

After final apply:

- Cython writes `level_cache[node_name] = level`
- returns to Python
- later river-step kernels consume state from river object arrays and boundary-face attrs

Current remaining Python ownership:

- Python dict update for `_internal_node_level_cache`
- Python object attribute ownership for boundary-face exported state
- Python-owned ghost-cell refresh semantics through `_refresh_cell_state(...)`

## remaining Python / Cython / C++ crossings

Inside the accepted nodechain hot path:

- Python boundary helper crossings: eliminated
- Python width lookup crossings: eliminated
- remaining crossings are concentrated in:
  - `river._refresh_cell_state(...)`
  - final face-state sync back into Python attrs
  - level-cache dict write-back

## repeated lookup / rebinding still present

The main repeated tail costs are now:

1. repeated Python `_refresh_cell_state(...)` dispatch after every exact closure
2. repeated Python attribute scatter in `sync_python_boundary_state()`
3. Python dict updates for final node level cache

These are the parts to push next before revisiting residual/Jacobian.
