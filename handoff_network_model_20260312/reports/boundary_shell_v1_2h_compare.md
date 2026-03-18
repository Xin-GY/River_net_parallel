# Boundary Shell V1 2h Compare

## Result

- strict compare: pass
- `allclose = true`

## Rows

- `cfl_history.csv`: `1483 / 1483`
- `internal_node_history.csv`: `1482 / 1482`

## First Diff

- `global_dt`: none
- `cfl_history.csv`: none
- `internal_node_history.csv`: none

## Timing

- baseline model/evolve: `2.7623345851898193 s`
- final exact candidate model/evolve: `2.574141502380371 s`

## Notes

The final exact candidate remains clean at 2h, so 40h gate was valid to run.
