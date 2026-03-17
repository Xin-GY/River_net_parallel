# Assemble Deep 10m Compare

- strict compare: pass
- `allclose = true`
- `cfl_history.csv` rows: `182 / 182`
- `internal_node_history.csv` rows: `181 / 181`
- first diff: none
- evolve/model time:
  - accepted historical `9a7c094`: `0.912919 s`
  - fresh replay: `0.926752 s`
  - candidate: `0.965080 s`

Conclusion:

- exactness holds
- short-case speed does not improve
