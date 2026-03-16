# Nodechain Commit Deep Implementation

## Files changed

- `handoff_network_model_20260312/cython_node_iteration.pyx`
- `handoff_network_model_20260312/Rivernet.py`
- `handoff_network_model_20260312/Islam.py`
- `handoff_network_model_20260312/tools/profile_cpp_exact_serial.py`

## Implementation summary

### 1. `cython_node_iteration.pyx`

Added native face-state export on the deep plan:

- `NodeBoundaryDeepPlan.export_face_state()`

Added a new exact flag path:

- `use_commit_deep = net.use_cpp_nodechain_commit_deep and use_deep_apply`

Changed final apply behavior:

- old path:
  - `deep_plan.apply_level(...)`
  - `deep_plan.sync_python_boundary_state()`
- new commit-deep path:
  - `deep_plan.apply_level(...)`
  - keep face state in native cache
  - do not synchronize back to Python boundary attributes in final apply

### 2. `Rivernet.py`

Added runtime option:

- `self.use_cpp_nodechain_commit_deep = False`

Extended nodechain plan build:

- clear any stale per-river deep-plan refs
- attach the built deep plan back to the owning river:
  - `_nodechain_deep_plan_left`
  - `_nodechain_deep_plan_right`

Added cached face-state accessor:

- `_get_boundary_face_state_cached(river, side)`

The accessor prefers the native deep-plan cache when commit-deep is enabled, then falls back to Python boundary-face attributes.

Switched these consumers to cached reads:

- `Caculate_node_Ac_at_ghost_cell_JPWSPC`
- node mass residual helpers
- `_record_internal_node_history_current_state`

### 3. `Islam.py`

Wired env config:

- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP`

### 4. `tools/profile_cpp_exact_serial.py`

Added CLI flag:

- `--use-cpp-nodechain-commit-deep`

The profiling harness now writes the flag into the environment and records it in the summary JSON.

## What changed operationally

Before this step, exact nodechain deep apply already owned closure-time face state, but final apply still scattered that face state back into Python boundary-face attributes.

After this step:

- final apply can remain native-owned
- later exact consumers can read the authoritative face state directly from the deep plan cache
- Python boundary attribute scatter is removed from the exact hot tail when the feature flag is enabled

## What did not change

- node iteration math
- closure call count
- residual / Ac formulas
- stopping checks
- update order
- float precision
- Python fallback behavior when the flag is off
