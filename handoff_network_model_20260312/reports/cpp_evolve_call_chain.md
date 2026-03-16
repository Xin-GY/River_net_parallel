# C++ Exact Evolve Call Chain

## Scope

- branch: `feature/cpp-exact-evolve-kernelize-next`
- start point: `835cf1f`
- timing scope: `evolve/model time` only
- execution mode analyzed here:
  - `ISLAM_USE_PARALLEL=0`
  - `ISLAM_FAST_MODE=0`
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`

## Entry Chain

### Prepare path

1. `Islam.prepare_net_for_evolve(net, yield_step)`  
   caller: benchmark harness or `Islam.run_prepared_evolve` setup  
   layer: Python  
   hot path: no  
   role:
   - optional Fine interpolation
   - initialize river states
   - save initial output metadata
   - configure save scheduler
   - compute initial global CFL

2. `Islam.run_prepared_evolve(net, yield_step, print_progress=False)`  
   caller: benchmark harness  
   layer: Python  
   hot path: wrapper only  
   callee:
   - `Rivernet._run_prepared_evolve(yield_step)`

3. `Rivernet._run_prepared_evolve(yield_step)`  
   layer: Python  
   hot path: yes, but only as dispatcher  
   branches:
   - `cpp_run_network_evolve_serial(self, float(yield_step))` when `ISLAM_USE_CPP_EVOLVE=1`
   - fallback to `self._evolve_base(yield_step)` otherwise

## Current C++ bridge path

### Time loop owner

4. `cython_cpp_bridge.run_cpp_network_evolve_serial(net, yield_step)`  
   caller: `Rivernet._run_prepared_evolve`  
   layer: Cython + C++ extension boundary, but loop body still calls Python methods  
   loop: once per time step  
   hot path: yes  
   current behavior:
   - owns the outer while-loop
   - updates `current_sim_time`, counters, yield bookkeeping
   - still calls Python methods for every major substage of the step

This is the first key reason the bridge gain is small: the loop shell moved to compiled code, but the step body still re-enters Python repeatedly.

## Per-step exact evolve chain

### A. Network-level step orchestration

5. `Rivernet.Set_global_time_step(self.DT)`  
   caller: bridge loop / Python `_evolve_base`  
   layer: Python  
   hot path: yes  
   loop nesting:
   - once per step
   - inner loop over all rivers
   callee:
   - `River.set_next_dt(dt)` on each river

6. `Rivernet.Update_boundary_conditions()`  
   caller: bridge loop / Python `_evolve_base`  
   layer: Python  
   hot path: yes  
   callee:
   - `Update_external_boundary_conditions_V2()`
   - `Update_internal_boundary_conditions()`

### B. External boundary path

7. `Rivernet.Update_external_boundary_conditions_V2()`  
   caller: `Update_boundary_conditions`  
   layer: Python  
   hot path: yes  
   loop nesting:
   - once per step
   - loop over external boundary nodes
   - loop over connected rivers
   callee:
   - `River.InBound_In_Q2`
   - `River.InBound_In_Q`
   - `River.InBound_Fix_level_V2/V3`
   - `River.OutBound_Free_Outfall`
   - `River.OutBound_Fix_level_V2/V3`

### C. Internal-node exact chain

8. `Rivernet.Update_internal_boundary_conditions()`  
   caller: `Update_boundary_conditions`  
   layer: Python  
   hot path: yes  
   loop nesting:
   - once per step
   - internal iterative solver
   branches:
   - fast serial Cython shell: `_try_update_internal_boundary_conditions_cython()`
   - full Python fallback when unsupported flags are enabled

9. `Rivernet._try_update_internal_boundary_conditions_cython()`  
   caller: `Update_internal_boundary_conditions`  
   layer: Python  
   hot path: yes  
   role:
   - checks exact-support constraints
   - builds or reuses `_cython_nodechain_plan`
   - calls `cython_node_iteration.run_internal_node_iteration_exact(...)`

10. `Rivernet._build_cython_nodechain_plan()` / `_get_cython_nodechain_plan()`  
    caller: `_try_update_internal_boundary_conditions_cython`  
    layer: Python  
    hot path: plan build is cold; reuse path is warm but cheap  
    role:
    - compile node order
    - compile contiguous branch offsets
    - store `branch_rivers` tuple and side-code array

11. `cython_node_iteration.run_internal_node_iteration_exact(...)`  
    caller: `_try_update_internal_boundary_conditions_cython`  
    layer: Cython  
    hot path: yes, dominant nodechain kernel today  
    loop nesting:
    - once per step
    - iterative loop up to `max_iteration`
    - per node
    - per incident branch
    current subcalls still inside loop:
    - `river.OutBound_Fix_level_V2/V3`
    - `river.InBound_Fix_level_V2/V3`
    - `river.cross_section_table.get_width_by_area(...)`
    - Python attribute reads through `object river`

This is the second key reason the bridge gain is small: the nodechain shell is compiled, but the exact closure and geometry queries still bounce through Python objects on every node iteration.

### D. Optional internal-node history

12. `Rivernet._record_internal_node_history_current_state()`  
    caller: bridge loop / Python `_evolve_base` after boundary update  
    layer: Python  
    hot path: yes when output is enabled  
    role:
    - builds a per-step Python dict
    - traverses all internal nodes and connected branches
    - reads boundary-face and cell values into history rows

### E. River-step network dispatch

13. `Rivernet.Caculate_face_U_C_net()`  
    caller: bridge loop / Python `_evolve_base`  
    layer: Python  
    hot path: yes  
    callee:
    - `call_river_function_by_name("Caculate_face_U_C")`

14. `Rivernet.Caculate_Roe_matrix_net()`  
    caller: bridge loop / Python `_evolve_base`  
    layer: Python  
    hot path: yes  
    callee:
    - `call_river_function_by_name("Caculate_Roe_matrix")`

15. `Rivernet.Caculate_Source_term_net()`  
    caller: bridge loop / Python `_evolve_base`  
    layer: Python  
    hot path: yes  
    callee:
    - `call_river_function_by_name("Caculate_source_term_2")`

16. `Rivernet.Caculate_Roe_flux_net()`  
    caller: bridge loop / Python `_evolve_base`  
    layer: Python  
    hot path: yes  
    callee:
    - `call_river_function_by_name("Caculate_Roe_Flux_2")`

17. `Rivernet.Assemble_flux_net()`  
    caller: bridge loop / Python `_evolve_base`  
    layer: Python  
    hot path: yes  
    callee:
    - `call_river_function_by_name("Assemble_Flux_2")`

18. `Rivernet.Update_cell_property_net()`  
    caller: bridge loop / Python `_evolve_base`  
    layer: Python  
    hot path: yes  
    callee:
    - `call_river_function_by_name("Update_cell_proprity2")`

19. `Rivernet.call_river_function_by_name(function_name)`  
    caller: each network dispatch stage above  
    layer: Python  
    hot path: yes  
    loop nesting:
    - once per stage
    - loop over all rivers
    role:
    - cached bound-method lookup
    - still calls Python methods one river at a time

This is the third key reason the bridge gain is small: even after entering the C++ bridge loop, each river-step stage still returns to Python and dispatches Python bound methods per river.

## River-step call chain

Per river, per step, the current default exact path is:

1. `River.Caculate_face_U_C()`  
   layer: Python + NumPy vector ops

2. `River.Caculate_Roe_matrix()`  
   layer: Python + NumPy vector ops

3. `River.Caculate_source_term_2()`  
   layer: Python outer loop

4. `River.Caculate_Roe_Flux_2()`  
   layer: Python dispatch  
   branches:
   - rectangular HR
   - general HR
   - default Roe
   current accepted fast exact serial path often uses `cython_river_kernels.fill_general_hr_flux_exact(self)` for general-HR interfaces

5. `River.Assemble_Flux_2()`  
   layer: Python orchestration  
   callee:
   - `_apply_explicit_conservative_increment()`
   - `_apply_explicit_friction_substep()`
   - `_enforce_explicit_conservative_admissibility()`

6. `River.Update_cell_proprity2()`  
   layer: Python loop by default  
   optional Cython:
   - `cython_river_kernels.update_cell_properties_exact(self)`

7. `Rivernet.Caculate_global_CFL()`  
   layer: Python  
   loop over rivers  
   callee:
   - `River.Caculate_CFL_time_for_river_net()`

## Layer summary of the current bridge line

### Already compiled

- outer while-loop shell in `cython_cpp_bridge.pyx`
- output-buffer storage in `cpp/output_buffer.*`
- optional nodechain shell in `cython_node_iteration.pyx`
- optional general-HR flux shell in `cython_river_kernels.pyx`

### Still effectively Python-owned

- boundary updater orchestration
- external boundary application
- node boundary closure methods
- node aggregate geometry queries
- per-stage river dispatch through `call_river_function_by_name`
- `Assemble_Flux_2` orchestration
- default `Update_cell_proprity2` loop
- global CFL reduction
- most per-step history/save decisions

## Why the current bridge only saves about 0.84 s over 40h

1. The bridge moved the time-loop shell, not the dominant numeric work.
2. The nodechain still uses Python river objects and Python boundary closures inside every iteration.
3. The river-step still crosses back into Python six to eight times per step.
4. `call_river_function_by_name` still dispatches cached Python bound methods for every river and every stage.
5. Output/history logic still builds Python objects when enabled.
6. The only real C++ storage object today is `OutputBuffer`; the numeric state still lives in Python-owned river objects.

## Immediate kernelization target implied by this call chain

1. Native C++ node iteration kernel with precompiled integer plans and direct array access.
2. Native C++ river-step kernels for the profiled Top 3 hotspots.
3. A native fullchain per-step entry that eliminates repeated Python method dispatch inside the step body.
