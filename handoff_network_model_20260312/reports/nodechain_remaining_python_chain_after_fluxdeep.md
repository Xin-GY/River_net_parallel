## Scope

Accepted exact configuration carried into this branch:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`

This report tracks only the nodechain inside `boundary_updater`.

## Real entry chain

1. `Islam.run_prepared_evolve`
   - layer: Python
   - hot path: yes
2. `Rivernet.Evolve -> _evolve_base`
   - layer: Python
   - hot path: yes
3. `Rivernet.Update_boundary_conditions`
   - layer: Python orchestration
   - hot path: yes
4. `Rivernet.Update_internal_boundary_conditions`
   - layer: Python orchestration
   - hot path: yes
5. `_try_update_internal_boundary_conditions_cython`
   - layer: Python dispatch
   - hot path: yes
6. `cython_run_internal_node_iteration_exact(...)`
   - layer: Cython
   - hot path: yes

## Nodechain stage-by-stage ownership

### 1. Predictor

- current layer: Cython loop
- remaining Python ownership:
  - still calls Python methods for initial node level source:
    - `Caculate_node_average_level_at_real_cell`
    - `Caculate_node_average_level_at_ghost_cell`
  - still touches Python cache dict `net._internal_node_level_cache`
- main cost type:
  - Python object access, but not dominant

### 2. apply target level / boundary closure

- current layer: mixed Cython + Python river objects
- accepted fast path today:
  - Cython iterates node -> branch
  - each branch calls `river._stage_boundary_fix_level_cython_prebound_fast(side_code, level)`
  - that method:
    - resolves cached closure context on Python river
    - calls `cython_compute_stage_boundary_mainline_fast(...)`
    - calls `_commit_stage_boundary_state_prebound(...)`
    - `_commit_stage_boundary_state_prebound(...)` calls `_refresh_cell_state(...)`
- remaining Python ownership:
  - one Python method call per closure
  - Python river object attribute dispatch for every closure
  - Python commit helper per closure
  - Python `_refresh_cell_state` per closure
- repeated per-iteration work still happening:
  - closure method dispatch
  - boundary-face attribute assignment
  - dry/near-dry state refresh bookkeeping
- this is the largest remaining nodechain sub-gap

### 3. aggregate / residual assembly

- current layer: Cython loop, but with Python object-backed river state
- remaining Python ownership:
  - per-branch width lookup via `river.cross_section_table.get_width_by_area(...)`
  - repeated `getattr(...)` on boundary-face attributes
  - Python object access for `river.S`, `river.Q`, `river.cell_sections`
- repeated per-iteration work:
  - width lookup on ghost/cell area
  - boundary-face field lookup
  - per-branch river object dereference

### 4. `Ac` assembly

- current layer: same Cython loop as residual
- remaining Python ownership:
  - same width lookup and per-branch object access pattern
  - no persistent native workspace for per-branch hydraulic scratch
- cost type:
  - object access + repeated lookup, not pure math

### 5. Jacobian / Newton support

- current accepted path:
  - disabled
  - cython exact path only runs when numeric Jacobian / coupled Newton are off
- current layer: not in accepted hot path
- action priority: none for this branch phase

### 6. stopping checks / level update

- current layer: Cython
- remaining Python ownership:
  - minimal
  - mostly native scalar update already
- action priority: low

### 7. final apply

- current layer: same pattern as apply target level / boundary closure
- remaining Python ownership:
  - again calls Python prebound fast closure method per branch
  - again goes through Python commit helper and `_refresh_cell_state`
- cost type:
  - closure/commit dispatch repeated once more after convergence

### 8. state commit / write-back

- current layer: split
  - Cython writes final levels into cache dict
  - Python river objects still own committed ghost/cell derived state
- remaining Python ownership:
  - boundary-face fields live as Python attributes
  - ghost-cell refresh and derived-state writeback still owned by Python helper code
- repeated/relookup issue:
  - no persistent native state-commit workspace

## Current repeated marshaling / lookup sources

- Python river method call for every accepted fast closure
- Python `_refresh_cell_state` for every accepted fast closure and final apply
- per-branch width lookup from Python cross-section object methods during residual/`Ac`
- boundary-face values stored as Python attributes and re-read through `getattr`
- cache dict update for final node level cache

## Conclusion

The remaining nodechain native gap is not in solver math shape. It is in ownership:

1. `apply_and_boundary_closure` still spends substantial time bouncing through Python river helpers
2. residual/`Ac` still spends repeated per-branch object lookup and width lookup overhead
3. final apply / state commit repeats the same Python-owned commit path
