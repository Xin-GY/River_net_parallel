# Nodechain Cython Implementation

## Scope

This branch adds an exact, single-process Cython path for the network internal-node iteration chain. The goal is to remove Python orchestration overhead from the hottest serial node-coupling loop without changing the numerical method.

## Files

- `cython_node_iteration.pyx`
- `build_cython_exact_kernels.py`
- `Rivernet.py`
- `Islam.py`

## Entry Point

- Runtime flag:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
- Python caller:
  - `Rivernet.Update_internal_boundary_conditions()`
- Python gate:
  - `Rivernet._cython_nodechain_supported()`
- Python plan builder:
  - `Rivernet._build_cython_nodechain_plan()`
- Python dispatcher:
  - `Rivernet._try_update_internal_boundary_conditions_cython()`
- Cython entry:
  - `cython_node_iteration.run_internal_node_iteration_exact(...)`

## What Moved To Cython

The Cython kernel owns the serial exact node-iteration loop:

1. build the per-node initial level guess from the same precedence as Python
2. iterate over nodes and incident branches in the same order as Python
3. call exact branch boundary closure on each river side
4. assemble node residual `pure_q`
5. assemble node `Ac`
6. apply the same clipped Newton-like update
7. check the same stopping conditions
8. do the final synchronized boundary apply
9. write back `_internal_node_level_cache`

## What Stayed In Python

- scenario and graph construction
- branch classification and cache refresh
- plan construction for node order and incident branches
- runtime routing and fallback selection
- diagnostics / reporting / high-level `Evolve` control

## Data Binding Strategy

The Cython path still uses exact live river objects, but removes the repeated Python shell around them.

Prebound inputs:

- `node_names`
- `node_offsets` as a contiguous `int32` array
- `branch_rivers` in fixed serial order
- `branch_side_codes` as a contiguous `int8` array

This preserves:

- node order
- per-node branch order
- residual accumulation order
- final boundary-apply order

## Exactness Rules Followed

- float64 math for node-level iteration variables
- same boundary-closure methods as Python:
  - `OutBound_Fix_level_V2/V3`
  - `InBound_Fix_level_V2/V3`
- no response table
- no predictor approximation beyond the existing exact last-level reuse
- no multiprocessing
- no reordering of branch accumulation
- no float32 substitution
- no threaded Cython

## Why This Cut Is Reasonable

The low-level stage-boundary closure was already going through exact Cython fast subpaths in the accepted baseline. The remaining nodechain cost sat above that level in:

- repeated Python node traversal
- repeated branch traversal
- Python dict lookups for node levels
- small-object and method-dispatch overhead

The new kernel therefore targets the orchestration shell, not the mathematical closure formula itself.
