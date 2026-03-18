# Source Deep V1 2h Compare

## Verdict

- strict compare: pass
- `allclose = true`

## Rows

- `cfl_history.csv`: `1483 / 1483`
- `internal_node_history.csv`: `1482 / 1482`

## First Diff

- first diff: none
- first diff time: none
- first diff cell / river / source-stage index: none

## Global DT

- `global_dt max_abs = 0.0`

## Timing

- baseline 2h model time: `2.09973406791687 s`
- candidate 2h model time: `2.1027448177337646 s`

## Note

The 2h full-case total is effectively flat, but the source-stage timer still drops materially:

- `river_dispatch.Caculate_source_term_2.time`: `0.050373 s -> 0.015591 s`
- `river_step.source`: `0.051877 s -> 0.017053 s`
