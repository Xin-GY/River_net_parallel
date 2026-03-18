# Final CPP After UpdateCell V2 Recommendation

## Verdict

This round does **not** produce a new accepted exact candidate.

## Why It Stops At Audit

Fresh audit overturns the initial assumption behind `updatecell_v2`.

Although `river_step.update_cell` is still larger than `assemble` and `source`, the accepted code already places almost all of the meaningful update-cell work inside the native kernel:

- state derivation
- width resolution
- dry/wet guards
- `water_level` / `water_depth` / `U` / `C` / `FR` write-back
- `P` / `PRESS` / `R` write-back
- `QIN` zeroing

The remaining visible Python/Cython shell around `Update_cell_proprity2` is too thin to justify a new continuation branch implementation.

## Current Accepted Exact Baseline

The accepted exact result remains:

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: `c92a3ca`
- 40h `evolve/model time = 34.26593613624573 s`

## Answering The Round Questions

1. `updatecell_v2` does not beat `c92a3ca` because no candidate was implemented.
2. The accepted 40h exact result remains `34.26593613624573 s`.
3. The round stops because there is no longer a large clean wrapper/state-exposure shell around `Update_cell_proprity2` to push down.
4. The raw remaining first-order blocker is still `nodechain / boundary_updater`.
5. If a future round continues, it should only proceed with a materially new idea in that family, not by reopening:
   - refresh deep
   - residual / Jacobian deep
   - fullstep / dispatch reshaping
   - boundary grouped-evaluator batching
6. It is not worth entering any C++ threads implementation right now.
7. Previously rejected directions remain rejected and should not be reopened.

## Recommendation

Keep `c92a3ca` as the accepted exact baseline and stop this continuation at the audit checkpoint.
