# Accepted Exact First-Order Blockers

## Real First-Order Blockers

### 1. Rectangular Roe flux remaining ownership

- evidence:
  - fresh 40h timer bucket: `river_step.flux = 42.333267 s`
  - 2h cProfile:
    - `_caculate_roe_flux_rectangular_hr = 3.408339 s`
    - `_compute_rectangular_hr_interface_flux = 3.170979 s`
    - `_solve_rectangular_hr_roe_flux = 1.731337 s`
- why still large:
  - Python still owns the rectangular per-face outer loop
  - interface state is built as Python dicts
  - repeated gather/scatter happens in Python
  - each face still walks through multiple Python helper calls before hitting scalar math

### 2. Nodechain orchestration tail

- evidence:
  - `nodechain.total = 38.318935 s`
  - `nodechain.apply_and_boundary_closure = 15.655460 s`
  - `nodechain.final_apply = 2.479389 s`
- why still large:
  - ownership is mixed between Python/Cython/native helpers
  - boundary-updater shell is still Python-owned
  - tail refresh/commit logic still coordinates across layers
- why not selected this round:
  - the obvious deeper refresh variants are already in the no-go set
  - residual/Jacobian is already too small to justify priority

### 3. Assemble tail

- evidence:
  - `river_step.assemble = 7.132460 s`
- why still large:
  - exact kernel exists, but river object ownership and stage-shell orchestration remain on the Python side

### 4. Update-cell tail

- evidence:
  - `river_step.update_cell = 4.027083 s`
- why still large:
  - kernel exists, but surrounding state refresh / state exposure are still mixed-ownership

### 5. Global CFL / dt reduction

- evidence:
  - `dt_update.global_cfl = 3.778728 s`
- why still large:
  - reduction is still Python/NumPy-owned and happens every step

## Tail Costs, Not First-Order

- `river_step.source = 1.911698 s`
- `river_step.roe_matrix = 1.684819 s`
- `river_step.face_uc = 0.808972 s`
- `nodechain.residual_and_ac = 0.232093 s`

These still matter, but none of them dominate the 40h full-case the way rectangular Roe flux does.

## Already Rejected Directions

Do not revisit these on this branch family without materially new evidence:

- `_refresh_cell_state` deeper ownership
  - inline Cython refresh: not exact
  - single-cell C++ exact refresh: exact but slower
- residual / Jacobian deep push
  - share too small
- fullstep native loop
  - not yet justified as first-order blocker
- build-flag experiments
  - `-march=native` explicitly rejected
- dispatch / bridge shape experiments
  - short-case wins with 40h regressions already documented

## Decision

The current first-order blocker is clearly the remaining Python ownership in rectangular Roe flux, not the previously rejected refresh/fullstep/build-flag routes.
