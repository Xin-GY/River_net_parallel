# Assemble Deep 40h Compare

- strict compare: pass
- `allclose = true`
- `cfl_history.csv` rows: `29784 / 29784`
- `internal_node_history.csv` rows: `29783 / 29783`
- first diff: none
- evolve/model time:
  - accepted historical `9a7c094`: `65.237010 s`
  - fresh replay: `74.175709 s`
  - candidate: `68.212999 s`

Conclusion:

- exactness holds on the full case
- candidate beats the clean replay
- candidate does **not** beat the accepted historical baseline, so it cannot replace `9a7c094`
