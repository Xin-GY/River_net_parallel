# Boundary Shell V1 10m Compare

## Result

- strict compare: pass
- `allclose = true`

## Rows

- `cfl_history.csv`: `182 / 182`
- `internal_node_history.csv`: `181 / 181`

## First Diff

- `global_dt`: none
- `cfl_history.csv`: none
- `internal_node_history.csv`: none

## Timing

- baseline model/evolve: `0.3388028144836426 s`
- final exact candidate model/evolve: `0.36406993865966797 s`

## Notes

10m remained exact after removing grouped evaluator reuse and restoring original callable argument semantics.
