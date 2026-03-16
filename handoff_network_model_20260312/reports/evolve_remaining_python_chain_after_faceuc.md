## Scope

Accepted exact configuration:

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

This report tracks only the `evolve/model time` path.

## Step Chain

### Entry

- `Islam.prepare_net_for_evolve`
  - caller: benchmark/profile entrypoints
  - role: prepare runtime state before evolve
  - hot path: no
  - layer: Python
- `Islam.run_prepared_evolve`
  - caller: benchmark/profile entrypoints
  - callee: `Rivernet.Evolve`
  - hot path: yes
  - layer: Python
- `Rivernet.Evolve`
  - caller: `run_prepared_evolve`
  - callee: `_evolve_base`
  - hot path: yes
  - layer: Python

### Per-step chain

1. `Rivernet.Update_boundary_conditions`
   - layer: Python orchestration
   - hot path: yes
   - still contains Python control flow for external BC and internal node update dispatch
   - crossing: Python -> Cython for internal node exact path

2. `Rivernet.Update_internal_boundary_conditions`
   - accepted path dispatches into `_try_update_internal_boundary_conditions_cython`
   - hot path: yes
   - layer: Python orchestration + Cython numeric chain
   - remaining Python:
     - nodechain entry dispatch
     - plan ownership on Python side
     - perf accounting and final orchestration

3. `cython_run_internal_node_iteration_exact(...)`
   - layer: Cython
   - hot path: yes
   - current native depth:
     - branch iteration loop is compiled
     - prebound fast closures are compiled and exact
   - remaining gaps:
     - residual / `Ac` / stopping logic still partly driven by Python-owned state and object methods
     - final write-back still depends on Python river objects
     - per-call width/general-chi/object access still not fully C++-owned

4. River-step dispatch from `Rivernet.call_river_function_by_name(...)`
   - layer: Python loop over rivers
   - hot path: yes
   - remaining gap:
     - each stage is still entered as a separate Python method call
     - this is not yet a native full-step loop

5. `River.Caculate_face_U_C`
   - layer: C++ exact kernel behind Python method
   - hot path: yes, but already mostly native
   - remaining Python loop: no
   - crossing: one Python -> Cython/C++ entry per river per step

6. `River.Caculate_Roe_matrix`
   - layer: C++ exact kernel behind Python method
   - hot path: yes, but already mostly native
   - remaining Python loop: no
   - crossing: one Python -> Cython/C++ entry per river per step

7. `River.Caculate_source_term_2`
   - layer: Python
   - hot path: moderate
   - remaining Python loop: yes, per-interface
   - object churn:
     - section lookup via `cell_sections[i]`
     - cross-section table lookup methods

8. `River.Caculate_Roe_Flux_2`
   - layer: mixed Python/Cython
   - hot path: yes, one of the largest remaining
   - accepted path:
     - general-HR path enters `_caculate_roe_flux_general_hr`
     - current best path uses `cython_fill_general_hr_flux_exact(self)`
   - remaining Python/Cython ownership gap:
     - per-face loop is compiled, but table ownership still enters via Python tuples of table objects
     - `compute_general_hr_flux_interface(...)` returns Python tuples
     - state gather/scatter and output writes are still mediated by Python-owned object arrays

9. `River.Assemble_Flux_2`
   - layer: mixed Python + C++ exact poststep
   - hot path: medium
   - accepted path:
     - conservative increment owner still entered from Python
     - explicit Manning poststep goes through C++
   - remaining gap:
     - stage orchestration and some state ownership remain outside C++

10. `River.Update_cell_proprity2`
   - layer: mixed Python + C++ exact kernel
   - hot path: medium
   - accepted path:
     - per-cell state refresh is already handled by C++
   - remaining gap:
     - Python still owns method dispatch and surrounding bookkeeping

11. CFL / `dt` update
   - layer: Python orchestration
   - hot path: smaller but still per-step
   - remaining gap:
     - global reduction and time-step commit are not yet folded into a native full-step loop

## Why 109.43 s Still Remains

Bridge/orchestration cleanup already removed some obvious wrapper overhead, but the remaining time is dominated by three ownership gaps:

- `Caculate_Roe_Flux_2` still spends large time in a compiled loop that is fed by Python object tuples and tuple-return helper calls.
- nodechain exact solve still has compiled closures, but residual / `Ac` / stopping / commit are not yet fully native-owned.
- one step is still decomposed into multiple Python-dispatched river methods, so Python/Cython/C++ boundary crossings remain at step granularity.

## Current crossing/object churn summary

- Python dispatch still exists at:
  - boundary updater entry
  - per-river stage fan-out
  - full-step stage sequencing
- Python object churn still exists at:
  - general-HR Roe flux table tuples and tuple-return interface helper
  - source-term section-name and cross-section-table method lookups
  - nodechain residual / `Ac` / final commit object coordination
- Fully native-owned today:
  - `face_uc`
  - `roe_matrix`
  - `update_cell`
  - assemble post-friction substep
