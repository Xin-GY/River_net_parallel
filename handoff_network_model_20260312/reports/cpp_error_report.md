# CPP Error Report

## Summary

`boundary_shell_v1` final exact candidate is numerically exact relative to the accepted serial path outputs in this branch.

All three gates pass:

- 10m: pass
- 2h: pass
- 40h: pass

## 10m

- `allclose = true`
- `cfl_history.csv` rows: `182 / 182`
- `internal_node_history.csv` rows: `181 / 181`
- first diff: none
- `global_dt max_abs = 0.0`

## 2h

- `allclose = true`
- `cfl_history.csv` rows: `1483 / 1483`
- `internal_node_history.csv` rows: `1482 / 1482`
- first diff: none
- `global_dt max_abs = 0.0`

## 40h

- `allclose = true`
- `cfl_history.csv` rows: `29784 / 29784`
- `internal_node_history.csv` rows: `29783 / 29783`
- first diff: none
- `global_dt max_abs = 0.0`

## Important Failed Sub-Variant

The first grouped-evaluator implementation was not exact on 40h:

- baseline steps: `29783`
- grouped candidate steps: `29810`
- first drift time: about `23399.751953125 s`

That grouped path is rejected and not the final candidate.
