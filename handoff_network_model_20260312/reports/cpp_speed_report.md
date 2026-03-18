# CPP Speed Report

## Summary

No new speed candidate was produced in the `updatecell_v2` round.

The continuation stopped at phase 1 after fresh audit showed that the accepted update-cell stage is already largely native-owned and that the remaining stage cost is not dominated by a removable Python/Cython wrapper shell.

## Current Accepted Reference

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: `c92a3ca`
- 40h `evolve/model time = 34.26593613624573 s`

## Fresh Audit Evidence

Current accepted 40h stage costs from the accepted branch-local reports:

- `nodechain.total = 26.428349 s`
- `boundary_updater.total = 25.179718 s`
- `river_step.update_cell = 1.729327 s`
- `river_step.assemble = 1.597568 s`
- `river_step.source = 0.329018 s`

Fresh local 2h accepted-config attribution:

- `river_dispatch.Update_cell_proprity2.time = 8.398995 s`
- `river_dispatch.Assemble_Flux_2.time = 5.926860 s`
- `river_dispatch.Caculate_source_term_2.time = 0.096814 s`
- `river_for_net.Update_cell_proprity2`: `tottime = 0.155999 s`, `cumtime = 8.383633 s`

Interpretation:

- `update_cell` is still larger than `assemble` and `source`
- but the remaining cost is mostly inside the accepted native kernel rather than in a large removable wrapper shell
- that makes a shell-only `updatecell_v2` continuation low-confidence

## Outcome

- accepted baseline before this round: `34.26593613624573 s`
- new `updatecell_v2` candidate: not created
- accepted result after this round: unchanged
