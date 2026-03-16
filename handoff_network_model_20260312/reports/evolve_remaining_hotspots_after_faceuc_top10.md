## Source

Primary ranking source: current accepted exact configuration, single-process, 2h profile in:

- `reports/cpp_fluxresidual_accepted_2h_perf.json`

40h accepted perf from previous identical accepted code path was used only as a consistency check for ranking, not as the primary measurement source.

## Top 10 Remaining Hotspots

1. `nodechain.total` = `5.383685860957485 s`
   - main cause: exact node iteration still owns substantial residual/`Ac`/convergence/commit work outside deep native ownership
2. `boundary_updater.total` = `3.4945216947235167 s`
   - main cause: nodechain plus external boundary orchestration
3. `river_dispatch.Caculate_Roe_Flux_2.time` = `2.152903917536605 s`
   - main cause: heavy per-face numeric loop plus remaining table/state ownership gap
4. `nodechain.apply_and_boundary_closure` = `2.285983848152682 s`
   - main cause: exact branch closure path, still partly object-driven around compiled closures
5. `river_dispatch.Assemble_Flux_2.time` = `0.31755078985588625 s`
   - main cause: stage ownership still split across Python + native poststep
6. `boundary_updater.external` = `0.7321565877646208 s`
   - main cause: Python-level external BC orchestration and interpolation dispatch
7. `nodechain.final_apply` = `0.2155174431973137 s`
   - main cause: final exact write-back/commit still not fully native-owned
8. `nodechain.residual_and_ac` = `0.15333078027470037 s`
   - main cause: residual/`Ac` logic still not deeply native-owned
9. `river_dispatch.Update_cell_proprity2.time` = `0.14609680307330564 s`
   - main cause: already nativeized but still invoked as a separate stage
10. `river_dispatch.Caculate_source_term_2.time` = `0.08909544226480648 s`
   - main cause: Python per-interface loop with table lookups

## Explicit Top 3

1. `nodechain.total`
   - dominant type: mixed numeric loop + Python/Cython ownership gap
2. `Caculate_Roe_Flux_2`
   - dominant type: numeric loop + Python/Cython table/state ownership
3. `boundary_updater.total`
   - dominant type: orchestration wrapper over nodechain/external BC

For actual pushdown work, this ranking is interpreted as:

1. deepen `Caculate_Roe_Flux_2` ownership
2. deepen nodechain residual/`Ac`/commit ownership
3. reduce full-step crossings after the first two are pushed down

That ordering matches the fact that:

- `face_uc`, `roe_matrix`, `update_cell`, and part of `assemble` are already native
- direct-dispatch style bridge reshaping has already been shown to help short runs but hurt 40h
- the current missing gains are inside ownership and dataflow, not in another dispatch topology experiment
