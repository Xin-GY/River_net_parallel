# Boundary Shell V1 40h Compare

## Result

- strict compare: pass
- `allclose = true`

## Rows

- `cfl_history.csv`: `29784 / 29784`
- `internal_node_history.csv`: `29783 / 29783`

## First Diff

- `global_dt`: none
- `cfl_history.csv`: none
- `internal_node_history.csv`: none

## Timing

Same-harness fresh replay:

- baseline model/evolve: `43.93435072898865 s`
- final exact candidate model/evolve: `44.53874897956848 s`

Historical accepted reference from source branch:

- accepted exact baseline `445c2c9`: `47.05382442474365 s`

## Notes

The grouped-shell attempt was faster but failed exact compare. The repaired final exact candidate passes 40h compare, but on the same local replay harness it regresses relative to baseline. This is the deciding reason not to promote it.
