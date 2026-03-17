# Accepted Exact Native Gap Map After Rect Flux

This map is based on the accepted exact path at `9a7c094`, reprofiled in the clean
continuation worktree.

## One full step, top-down

1. `Update_boundary_conditions`
   - Ownership: mixed
   - Internal node part:
     - substantial native ownership already exists through
       `cython_node_iteration.run_internal_node_iteration_exact`
     - deep apply / commit and prebound fast closures are already active
   - External boundary part:
     - still mostly Python-owned
     - `boundaries` dict lookup
     - Python callable dispatch
     - scalar interpolation through `PersistentLinearInterpolator`
     - Python node-to-river fan-out

2. `Caculate_face_U_C`
   - Ownership: substantial native-owned
   - Remaining gap:
     - Python wrapper / dispatch around the kernel

3. `Caculate_Roe_matrix`
   - Ownership: substantial native-owned
   - Remaining gap:
     - Python wrapper / dispatch around the kernel

4. `Caculate_source_term_2`
   - Ownership: still mainly Python / NumPy
   - Remaining gap:
     - pure Python ownership
     - state gather and per-river orchestration

5. `Caculate_Roe_Flux_2`
   - Ownership: substantial native-owned
   - General-HR path:
     - deep native plan already exists
   - Rectangular path:
     - deep native plan now exists and is the reason this baseline got much faster
   - Remaining gap:
     - wrapper ownership and non-primary branches only

6. `Assemble_Flux_2`
   - Ownership: partial native-owned
   - Remaining gap:
     - outer ownership still in Python
     - gather/scatter and write-back not fully native-owned

7. `Update_cell_proprity2`
   - Ownership: partial native-owned
   - Remaining gap:
     - wrapper ownership and state write-back still partly Python-side

8. `Caculate_global_CFL`
   - Ownership: still Python-owned
   - Remaining gap:
     - per-river loop
     - global min reduction

9. Save / history / bookkeeping
   - Ownership: Python
   - Not the primary blocker for this round

## Substantial native-owned already

- nodechain deep apply
- nodechain commit deep
- nodechain fast closure path
- general-HR Roe flux deep path
- rectangular Roe flux deep path
- face-UC helper
- Roe matrix helper

## Still only native-helper, not full ownership

- external boundary exact chain
- assemble
- update-cell
- dt/cfl reduction
- parts of source term

## Fresh takeaway

After the rectangular Roe flux ownership push, the cleanest remaining native gap is no
longer inside the already-optimized nodechain core. It is the external boundary exact
update path, because it still keeps both data ownership and dispatch ownership in Python.
