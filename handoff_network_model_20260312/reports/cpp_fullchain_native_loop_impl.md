# C++ Fullchain Native Loop Implementation Notes

## Files Changed

- `Islam.py`
  - adds:
    - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH`
- `Rivernet.py`
  - stores:
    - `use_cpp_bridge_direct_dispatch`
- `cython_cpp_bridge.pyx`
  - adds direct per-step iteration over `net._river_edges`
  - replaces the network wrapper fan-out for:
    - set dt
    - face/U/C
    - Roe matrix
    - source term
    - Roe flux
    - assemble
    - update cell
    - save-step result
    - CFL reduction

## Exactness Fix Applied

The first direct-dispatch draft was faster, but it drifted because the direct CFL path did this:

- converted each candidate `dti` to `float`
- reduced the global dt using those converted values

That changed the future timestep sequence.

The accepted exact fix is:

- keep `dti` in its original object-valued form
- accumulate `dt_list`
- compute:
  - `net.cfl_allowed_dt = min(dt_list)`

With that change, the direct-dispatch bridge returned to exact agreement on 10m and 2h.

## Why This Helps

This phase does not introduce a new numeric kernel. The gain comes from shrinking one layer of repeated network wrapper orchestration around already-compiled kernels.

The bridge loop now owns more of the exact step choreography directly, instead of repeatedly calling back into:

- `Rivernet.Caculate_face_U_C_net`
- `Rivernet.Caculate_Roe_matrix_net`
- `Rivernet.Caculate_Source_term_net`
- `Rivernet.Caculate_Roe_flux_net`
- `Rivernet.Assemble_flux_net`
- `Rivernet.Update_cell_property_net`
- `Rivernet.Caculate_global_CFL`

## Remaining Limitation

The bridge is still not a fully native object model:

- each river phase still calls Python-bound river methods
- the nodechain is only partially native
- the river-step kernels are still mixed Python/Cython

So this phase is best understood as:

- a fullchain orchestration cleanup
- not yet the final C++ kernelization end state

## Outcome On This Branch

This implementation was exact after the dt-reduction fix, but it was not accepted as the new default candidate:

- 10m: faster
- 2h: faster
- 40h: slower than the accepted phase-3 wrapper-bypass path

That makes it a useful documented experiment, but not the branch’s current best exact configuration.
