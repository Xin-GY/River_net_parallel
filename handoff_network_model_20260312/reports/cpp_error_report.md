# CPP Error Report

## Summary

`assemble_deep_v2` is exact relative to the accepted global-CFL baseline outputs.

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

## Conclusion

The deeper assemble ownership push does not introduce any observed drift in:

- `cfl_history.csv`
- `internal_node_history.csv`
- control outputs
- final 40h state files
