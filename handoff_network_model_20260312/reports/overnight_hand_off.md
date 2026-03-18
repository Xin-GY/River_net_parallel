# Overnight Hand Off

## Current Branch

- branch: `feature/cpp-exact-after-source-updatecell-v2`
- latest checkpoint: phase-1 no-go documentation synced on this branch
- true accepted starting point for this round: `feature/cpp-exact-after-assemble-source-deep-v1@c92a3ca`

This branch is already at its final documentation checkpoint for the phase-1 no-go outcome.

## What This Round Did

- Stayed on the true accepted exact baseline `c92a3ca`.
- Re-audited only `Update_cell_proprity2`.
- Did not implement any new kernel or shell path after phase 1.

## Why The Round Stopped

Fresh audit showed that the accepted update-cell stage is already mostly native-owned.

The accepted kernel already owns:

- state derivation
- width resolution
- dry/wet guards
- derived-state write-back
- `QIN` zeroing

The remaining Python/Cython shell is too thin to justify a new `updatecell_v2` implementation.

## Fresh Evidence

Current accepted 40h stage costs from `c92a3ca` branch-local accepted reports:

- `nodechain.total = 26.428349 s`
- `boundary_updater.total = 25.179718 s`
- `river_step.update_cell = 1.729327 s`
- `river_step.assemble = 1.597568 s`
- `river_step.source = 0.329018 s`

Fresh local 2h accepted-config attribution:

- `river_dispatch.Update_cell_proprity2.time = 8.398995 s`
- `river_for_net.Update_cell_proprity2`: `tottime = 0.155999 s`, `cumtime = 8.383633 s`
- `river_for_net._refresh_cell_state`: `cumtime = 14.571875 s`

Important interpretation:

- `_refresh_cell_state` remains expensive globally
- but it is not being driven by the accepted update-cell stage itself
- so a wrapper-only `updatecell_v2` pass would not remove the real remaining cost center

## Current Conclusion

This round is a phase-1 no-go checkpoint.

- no new exact candidate was created
- accepted exact baseline remains `c92a3ca`
- accepted 40h `evolve/model time` remains `34.26593613624573 s`

## Remaining First-Order Blocker

Raw Top 1 remains:

- `nodechain.total`
- `boundary_updater.total`

But the remaining obvious deeper routes there are still too close to already rejected exact families:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch reshaping
- boundary grouped-evaluator batching

## Threads Recheck

Do not implement threads.

After the accepted source-deep round:

- `source` is too small
- `assemble` is smaller than before
- `update_cell` no longer presents a meaningful removable shell
- the remaining heavy stages are still the risky nodechain / boundary families

## Local State

Generated artifacts remain untracked and must stay out of the commit:

- `*.so`
- generated `*.c` / `*.cpp`
- `reports/*_summary.json`
- `reports/*_perf.json`
- `reports/*_compare.json`
- `reports/*.prof`
- `result/**`
