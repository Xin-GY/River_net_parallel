# After Source Next Audit Design Candidates

## Decision Rule

This audit must end with exactly one answer:

- one unique materially new candidate
- or `none`

Multiple parallel candidates are not allowed.

## Candidate Classification

| Family / stage | Fresh 40h signal | Class | Why |
| --- | ---: | --- | --- |
| `nodechain.apply_and_boundary_closure` | `11.717452 s` | `B` | Raw cost is huge, but the obvious next pushes still collapse back into refresh-state, boundary-face sync, residual, or commit-tail territory that is too close to already-rejected exact families. |
| `nodechain.final_apply` | `1.969999 s` | `B` | Same story as above: still part of the nodechain tail, not a clearly new serial ownership idea. |
| `boundary_updater.external` | `11.893754 s` | `B` | Boundary shell v1 already showed shell-only deepening can stay exact but does not deliver same-harness net gain; grouped batching fails 40h exact. |
| Python per-step stage fan-out (`call_river_function_by_name`) | `0.532409 s` over fresh 2h | `B` | Still real overhead, but this belongs to the already-rejected fullstep / dispatch-reshaping family. |
| `river_step.flux` / `Caculate_Roe_Flux_2` | `2.460760 s` | `D` | Numerically mid-sized, but the accepted runtime already uses deep rectangular-HR and deep general-HR flux kernels. Remaining code outside native ownership is mostly stage orchestration and resets, not a new first-order gap. |
| `river_step.update_cell` / `Update_cell_proprity2` | `2.076577 s` | `D` | Fresh `updatecell_v2` audit already showed the meaningful work is in the accepted native kernel and the surrounding shell is too thin. |
| `river_step.assemble` / `Assemble_Flux_2` | `1.837699 s` | `D` | Serial deep path is already accepted; follow-on threads audit is explicit no-go because grain size is too fine. |
| `river_step.source` / `Caculate_source_term_2` | `0.354537 s` | `C` | Already accepted deep and now too small to be the next move. |
| `river_step.roe_matrix` | `0.991126 s` | `C` | Already substantially native-owned and too small to justify a new exact round. |
| `river_step.face_uc` | `0.499876 s` | `C` | Same as above. |
| `dt_update.global_cfl` | `0.538512 s` | `C` | Already accepted deep and explicitly too small for threads or another serial round. |

## Why `flux` Is Not Class A

`flux` is the only non-nodechain stage that still looks medium-sized, so it is the only one that needed an explicit challenge here.

It still does **not** qualify as a materially new candidate because:

1. the accepted general-HR path already enters `cpp_fill_general_hr_flux_exact_deep(...)`
2. the rectangular-HR deep path is already accepted
3. the remaining Python-visible work is mostly stage setup / buffer reset / rain-source bookkeeping
4. that remaining shell is not clearly large enough to justify a new accepted round with realistic 40h net gain

So `flux` is not “rejected,” but it also does not clear the bar for “the one unique next implementation target.”

## Unique Result

`A class = none`

There is no single materially new exact-only serial candidate that is both:

- clearly outside the rejected families
- and large enough to justify a new implementation round

## Audit Conclusion

Stop implementation planning here.

Keep `c92a3ca` as the accepted exact baseline and do not start a new exact implementation branch yet.
