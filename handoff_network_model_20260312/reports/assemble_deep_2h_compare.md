# Assemble Deep 2h Compare

- strict compare: pass
- `allclose = true`
- `cfl_history.csv` rows: `1483 / 1483`
- `internal_node_history.csv` rows: `1482 / 1482`
- first diff: none
- evolve/model time:
  - accepted historical `9a7c094`: `6.680291 s`
  - fresh replay: `7.167058 s`
  - candidate: `6.509730 s`

Conclusion:

- exactness holds
- the deeper assemble path improves the clean replay and edges past the historical 2h timing
- this was enough to justify the 40h gate run
