# Accepted Exact First-Order Blockers After Rect Flux

This report ranks blockers for the currently accepted exact path on top of `9a7c094`.

## True first-order blockers

1. `boundary_updater.external`
   - 40h cost: `16.212713 s`
   - Why it is still large:
     - boundary ownership is still in Python
     - `self.boundaries` dict lookup on every step
     - Python lambda call on every external node
     - scalar interpolation through `PersistentLinearInterpolator.__call__`
     - repeated node-to-river dispatch in Python
   - 2h cProfile evidence:
     - `Update_external_boundary_conditions_V2`: `1.838 s`
     - `InBound_In_Q2`: `1.180 s`
     - `get_boundary_value`: `0.548 s`
     - `PersistentLinearInterpolator.__call__`: `0.507 s`
     - `q_boundary_value`: `0.468 s`

2. `river_step.assemble`
   - 40h cost: `6.566261 s`
   - Why it is still large:
     - native helper exists, but ownership and some gather/scatter still stay in Python
     - outer orchestration remains per-river Python-driven

3. `dt_update.global_cfl`
   - 40h cost: `3.936878 s`
   - Why it is still large:
     - pure Python per-river reduction loop
     - still relies on Python-owned result collection and global min reduction

4. `river_step.update_cell`
   - 40h cost: `3.405632 s`
   - Why it is still large:
     - helper exists, but ownership still partly in Python
     - state write-back and surrounding orchestration still above native ownership

5. `nodechain.final_apply`
   - 40h cost: `2.803407 s`
   - Why it is still visible:
     - tail ownership is not fully native
     - but it is no longer the strongest next move compared with the external boundary chain

## Large buckets that are not the right next move

- `nodechain.total`
  - still numerically large at `41.496887 s`
  - but the high-value native pushes already landed:
    - deep apply ownership
    - commit ownership
    - prebound fast closures
  - the remaining sub-buckets are no longer the cleanest next single blocker

- `nodechain.apply_and_boundary_closure`
  - still `16.989520 s`
  - but the remaining obvious route overlaps with the rejected `_refresh_cell_state` deeper
    ownership family; that is not the next move for this round

## Tail costs

- `river_step.source`
- `river_step.roe_matrix`
- `river_step.face_uc`
- `nodechain.residual_and_ac`
- `nodechain.update_and_stopping`
- save/history recording sub-buckets

These are real costs, but they are not currently first-order blockers.

## Explicit no-go directions for this round

- `_refresh_cell_state` deeper ownership old variants
- residual / Jacobian deeper push
- fullstep loop / dispatch shape experiments
- `-march=native`
- multiprocessing / threads benchmark routes
- FAST_MODE / approximation paths

## Conclusion

The new Top 1 blocker is not Roe flux anymore. It is the external boundary exact chain,
because it is both large enough on 40h and still clearly Python-owned.
