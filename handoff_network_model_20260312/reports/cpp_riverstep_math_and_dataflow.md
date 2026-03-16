# C++ River-Step Math And Dataflow

## Scope

This report covers the per-river exact step inside the network evolve loop. The focus is the explicit path used by the current single-process exact branch.

## Network-level river-step order

Within each global time step, after boundary updates are complete, the network calls the following river stages in order:

1. `Caculate_face_U_C_net`
2. `Caculate_Roe_matrix_net`
3. `Caculate_Source_term_net`
4. `Caculate_Roe_flux_net`
5. `Assemble_flux_net`
6. `Update_cell_property_net`
7. `Caculate_global_CFL`

Today these are still orchestrated from Python at the network layer, even under the C++ bridge.

## Per-river exact explicit step

### 1. `River.Caculate_face_U_C`

Role:

- compute face-averaged velocity `F_U`
- compute face wave speed `F_C`
- handle one-side-dry and both-dry face cases

Inputs:

- cell `S`, `U`, `C`
- cell wet/dry thresholds
- `PRESS` only indirectly through later stages

Outputs mutated in place:

- `F_U`
- `F_C`

Computation type:

- mostly vectorized NumPy
- still Python function entry and some array allocation per call

### 2. `River.Caculate_Roe_matrix`

Role:

- compute Roe eigenvalues and eigenvectors for each interface
- detect LeVeque wet/dry switching masks

Inputs:

- `F_U`, `F_C`
- `BETA`
- `FR`
- `water_depth`

Outputs mutated in place:

- `Lambda1`, `Lambda2`
- `Vactor1`, `Vactor2`
- transpose/helper arrays
- `flag_LeVeque`

Computation type:

- NumPy-heavy vector operations
- still Python-owned orchestration and state writes

### 3. `River.Caculate_source_term_2`

Role:

- compute explicit friction source term per interface

Inputs:

- neighboring cell `S`, `Q`
- `water_depth`
- section DEB values from cross-section tables

Outputs mutated in place:

- `friction_source`

Computation type:

- Python outer loop over interfaces
- repeated section-table lookup through Python object methods

### 4. `River.Caculate_Roe_Flux_2`

Role:

- compute interface numerical flux and hydrostatic reconstruction corrections

Branches:

1. rectangular HR flux
2. general HR flux
3. default Roe flux path

Accepted fast exact serial path today:

- general-HR branch can enter `cython_river_kernels.fill_general_hr_flux_exact(self)`

Outputs mutated in place:

- `Flux_LOC`
- `Flux_Source_left`
- `Flux_Source_right`
- `Flux_Friction_left/right`
- `Flux_Source_center`

Computation type:

- current best path is partially Cythonized
- still driven by Python river objects and Python-owned arrays

### 5. `River.Assemble_Flux_2`

Role:

- apply conservative increment
- apply explicit friction substep
- enforce post-update conservative admissibility

Outputs mutated in place:

- mainly `S` and `Q`

Computation type:

- Python orchestration calling several helpers
- less formula-heavy than flux, but still part of the hot chain

### 6. `River.Update_cell_proprity2`

Role:

- refresh derived state from updated conservative state
- recompute:
  - `water_level`
  - `water_depth`
  - `U`
  - `C`
  - `FR`
  - `P`
  - `PRESS`
  - `R`
- zero `QIN`

Accepted exact status today:

- default path is Python loop over all cells
- Cython candidate exists but is not accepted as exact because it still drifts on longer cases

Computation type:

- true hot loop
- repeated table lookups per cell
- strong ownership of final per-cell derived state

### 7. CFL update

Network side:

- `Rivernet.Caculate_global_CFL()`

Per river:

- `River.Caculate_CFL_time_for_river_net()`

Role:

- compute local stable `dt` candidate from `U`, `C`, `cell_lengths`
- network takes the minimum over rivers

Computation type:

- Python network reduction + NumPy per river

## Current execution layer map

### Already partially compiled

- general-HR exact flux helper in `cython_river_kernels.pyx`
- output-buffer append path through `CppOutputBuffer`

### Still Python/Cython-object heavy

- network stage dispatch
- source-term loop
- most of default Roe path
- `Assemble_Flux_2`
- default accepted `Update_cell_proprity2`
- CFL reduction at network level

## Why the river-step is still not native fullchain

1. The network still dispatches each stage separately from Python.
2. Each stage still operates on Python `River` objects rather than a native `RiverRuntime`.
3. Table references are only partially prebound; many calls still route through Python table objects.
4. The best compiled kernel today only covers part of `Caculate_Roe_Flux_2`.
5. The accepted exact path still falls back to Python for `Update_cell_proprity2`, which remains a major per-step cost.

## Real hot functions still not deeply native

Based on current structure, the most likely river-step hotspots are:

- `Caculate_Roe_Flux_2`
- `Update_cell_proprity2`
- `Caculate_source_term_2`
- followed by `Caculate_Roe_matrix` and `Caculate_face_U_C`

The exact Top 3 still needs to be confirmed by the current branch’s single-process evolve-only profile.

## Native C++ target for river-step

The eventual native fullchain river step should run as a single C++ entry over a `RiverRuntime`, not as six Python-dispatched phases. That requires:

1. contiguous SoA state arrays in C++
2. prebound `table_id -> CrossSectionTableCpp*`
3. native interface loops for:
   - face `U/C`
   - Roe matrix
   - source
   - flux
   - assemble
   - update cell properties
4. native local CFL candidate computation

Until that happens, the bridge remains mostly a compiled loop shell around Python-owned stage dispatch.
