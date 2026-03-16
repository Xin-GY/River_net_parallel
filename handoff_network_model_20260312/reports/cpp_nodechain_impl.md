# C++ Nodechain Implementation Notes

## Scope

This phase does not replace the full internal-node solve with a new C++ object model yet. It applies a safe exact cut inside the existing compiled nodechain shell.

## Files Changed

- `Islam.py`
  - adds runtime flag wiring:
    - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST`
- `Rivernet.py`
  - adds branch-local runtime attribute:
    - `use_cython_nodechain_direct_fast`
- `cython_node_iteration.pyx`
  - adds `_apply_stage_boundary_wrapper_bypass(...)`
  - uses that helper inside:
    - iterative node-level apply loop
    - final synchronized apply loop

## What The New Helper Does

`_apply_stage_boundary_wrapper_bypass(...)` is intentionally narrow:

- it does not introduce new math
- it does not build new surrogate state
- it simply asks the existing exact compiled boundary-closure fast path to handle the update directly

Equivalent logical routing:

- old path:
  - `InBound_Fix_level_V3` / `OutBound_Fix_level_V3`
  - inside wrapper:
    - try `_stage_boundary_fix_level_cython_fast(...)`
    - if accepted, return
    - else use full Python closure path
- new phase-3 path:
  - nodechain loop first tries `_stage_boundary_fix_level_cython_fast(...)`
  - if it accepts, the wrapper shell is skipped
  - if it rejects, control returns to the original wrapper path

## Why This Split Was Chosen

The earlier, deeper prototype attempted to:

- call `compute_stage_boundary_mainline_fast(...)` directly
- commit boundary state directly from the nodechain loop
- replace width lookups with table-ref direct calls

That route was not safe enough for the exact path:

- one variant segfaulted
- one variant produced small but real drift

The accepted wrapper-bypass cut is therefore the deepest exact-preserving change currently validated on this branch.

## Boundaries Still Not Eliminated

This phase does **not** yet remove:

- Python river objects
- Python state ownership for ghost-cell arrays
- `_refresh_cell_state(...)`
- `_set_boundary_face_state(...)`
- Python-controlled timestep loop

Those remain phase-4 / phase-5 work.
