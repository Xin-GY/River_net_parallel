# C++ Data Layout And Boundary Crossings

## Bottom line

The current bridge has exactness and a working compiled loop, but the hot path is still dominated by Python-owned state and repeated Python/Cython/C++ crossings. That is why 40h evolve improved by only about `0.84 s`.

## Current hot-path data structures

### Network-level Python objects

- `self._river_edges`
  - list of `(u, v, data)` edge triples
- `_in_branches_by_node` / `_out_branches_by_node`
  - dict: `node -> list[(river_obj, name)]`
- `_river_method_cache`
  - dict: `function_name -> list[(river_name, bound_method)]`
- `_internal_node_level_cache`
  - dict: `node_name -> level`
- `internal_node_history`
  - list of per-step Python dict rows

### River-level Python objects

- `River` instance as a large mutable object graph
- NumPy arrays for hydraulic state
- Python/extension cross-section table object
- many scalar flags stored as Python attributes

### Compiled-but-still-object-heavy structures

- `_cython_nodechain_plan`
  - `node_names`: Python tuple of node names
  - `branch_rivers`: Python tuple of `River` objects
  - `node_offsets`: NumPy int32 array
  - `branch_side_codes`: NumPy int8 array
- `cython_river_kernels` entry points still take `object river`

## Current Python costs that remain in the hot path

### 1. Python dict lookup

Still present in the step hot path:

- `_river_method_cache[function_name]`
- `_internal_node_level_cache[node]`
- `_in_branches_by_node[node]`
- `_out_branches_by_node[node]`
- `boundaries[node]`

### 2. String-based dispatch

Still present in the step hot path:

- `call_river_function_by_name("Caculate_face_U_C")`
- `call_river_function_by_name("Caculate_Roe_matrix")`
- `call_river_function_by_name("Caculate_source_term_2")`
- `call_river_function_by_name("Caculate_Roe_Flux_2")`
- `call_river_function_by_name("Assemble_Flux_2")`
- `call_river_function_by_name("Update_cell_proprity2")`

Even though bound methods are cached, the network still pays:

- function-name keyed dict lookup
- Python loop over rivers
- Python callable invocation for every river and phase

### 3. Small tuple/list/object construction

Still present or reused in hot-path-friendly-but-not-native form:

- `(river_obj, name)` branch tuples
- `(river_name, func)` cached method tuples
- per-step internal-node history row dicts
- temporary Python objects produced by Python method/property access

### 4. Section lookup through Python objects

Still present in nodechain and river-step:

- `river.cross_section_table.get_width_by_area(...)`
- `river.cross_section_table.get_area_by_depth(...)`
- other geometry table queries through Python-bound methods

### 5. Boundary crossings

The current “C++ bridge” step still crosses:

1. Python -> Cython/C++ once per evolve start
2. Cython -> Python once per step for `Update_boundary_conditions`
3. Python -> Cython for nodechain shell
4. Cython nodechain -> Python per branch closure call
5. Cython nodechain -> Python per table/attribute read
6. Cython bridge -> Python once per river-step stage
7. Python stage dispatcher -> Python bound method per river
8. Python -> C++ output buffer append when saving

The shell crossing is cheap. The repeated mid-step crossings are not.

## Current marshaling/copying still happening each step

### Boundary/history path

- per-step history dict row assembly when outputs are enabled
- conversion of many branch-end scalars into Python floats for logging/history

### Save path

Improved already:

- runtime output storage can use `CppOutputBuffer`

Still not fully native:

- `Save_result_per_time_step` still slices NumPy arrays and prepares contiguous arrays at append time
- final dataset materialization is still Python/xarray owned

### River-step path

- stage dispatch keeps state in Python `River` objects
- compiled kernels pull data from Python object attributes instead of from a native runtime struct

## Best candidate structures for native replacement

### Integer plans

Should become native:

- `node_offsets`
- `branch_river_ids`
- `branch_side_codes`
- `branch_flow_signs`
- `river_offsets` or static river list indices

### Contiguous arrays / SoA

Should move into a native `RiverRuntime`:

- `S`, `Q`, `U`, `C`, `FR`
- `water_level`, `water_depth`
- `PRESS`, `P`, `R`
- `cell_lengths`, `river_bed_height`
- `F_U`, `F_C`
- Roe arrays
- flux/source arrays
- local CFL workspace

### Prebound native table handles

Should replace string or object lookups:

- `cell_table_ids`
- `face_left_table_ids`
- `face_right_table_ids`
- `table_id -> CrossSectionTableCpp*`

### Persistent native workspace

Needed to stop repeated marshaling:

- node residual workspace
- node Ac workspace
- Newton/update workspace
- river-step scratch arrays
- save/output workspace

## Why the bridge only saved about 0.84 s

The answer from the current data layout is straightforward:

1. The only fully native persistent object today is the output buffer.
2. The time loop is compiled, but the network state is still stored and advanced in Python objects.
3. Nodechain “compiled” execution still dereferences Python `River` objects per branch.
4. River-step kernels are still entered as Python bound methods stage by stage.
5. There is no native `NetworkRuntime` or `RiverRuntime` holding the hot arrays yet.

So the bridge removed a small amount of outer-loop Python overhead, but the dominant work still sits behind repeated Python object access and cross-layer dispatch.

## Immediate conversion targets

### Highest-value next replacements

1. native node/branch plan:
   - integer node ids
   - integer river ids
   - contiguous incident-branch ranges
2. native node iteration workspace:
   - `levels`, `residuals`, `Ac`, `dz`
3. native river runtime state arrays
4. native fullchain step entry:
   - one per-step call, not six network stage callbacks

### Keep in Python for now

- scenario construction
- reading input files
- final report/export orchestration
- feature-flag routing

## Phase-1 conclusion

The limiting factor is no longer “do we have a compiled loop at all”. It is that:

- the numeric state still lives in Python objects
- the exact closures still execute through Python methods
- the step body still crosses boundaries too many times

That is why the next step has to be true kernelization, not more bridge scaffolding.
