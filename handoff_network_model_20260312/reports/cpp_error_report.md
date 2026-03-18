# CPP Error Report

## Summary

`source_deep_v1` is exact relative to the accepted `445c2c9` serial baseline under the local no-`h5netcdf` strict-compare harness.

All three gates pass:

- 10m: pass
- 2h: pass
- 40h: pass

The local helper harness was used because this machine still lacks a working `h5netcdf` install. The compare thresholds remained strict:

- `rtol = 1e-12`
- `atol = 1e-12`

and the compared artifacts still included:

- `cfl_history.csv`
- `internal_node_history.csv`
- saved output CSVs / netCDF files

## 10m

- `allclose = true`
- `cfl_history.csv` rows: `182 / 182`
- `internal_node_history.csv` rows: `181 / 181`
- first diff: none
- first diff time: none
- first diff cell / river / source-stage index: none
- `global_dt max_abs = 0.0`

## 2h

- `allclose = true`
- `cfl_history.csv` rows: `1483 / 1483`
- `internal_node_history.csv` rows: `1482 / 1482`
- first diff: none
- first diff time: none
- first diff cell / river / source-stage index: none
- `global_dt max_abs = 0.0`

## 40h

- `allclose = true`
- `cfl_history.csv` rows: `29784 / 29784`
- `internal_node_history.csv` rows: `29783 / 29783`
- first diff: none
- first diff time: none
- first diff cell / river / source-stage index: none
- `global_dt max_abs = 0.0`

## Conclusion

The serial exact source deepening does not introduce any observed drift in:

- `cfl_history.csv`
- `internal_node_history.csv`
- saved comparison outputs
- final 40h state files
