# Source Deep V1 Plan

## Goal

Push `Caculate_source_term_2` from Python per-interface ownership into a serial exact native path on top of the accepted `445c2c9` baseline.

## Scope

The new path is restricted to:

- per-interface left/right section table access
- DEB lookup
- friction/source assembly
- denominator clip handling
- `friction_source` write-back

The new path does **not** touch:

- nodechain families
- boundary shell families
- assemble
- update-cell
- threads

## Guardrails

- feature flag: `ISLAM_CPP_USE_SOURCE_DEEP=1`
- float64 semantics preserved for the output arrays
- same cell traversal order
- same lookup order
- same friction / DEB / guard / clip sequence
- same Python fallback when the flag is off

## Implementation Shape

1. Reuse the accepted left/right table preparation already available from the general-HR path.
2. Add a source-specific plan cache so source does not rebuild table views every step.
3. Add a C++ kernel that walks interfaces in serial order and computes exactly the same friction source as the current Python loop.
4. Route `River.Caculate_source_term_2()` through the new kernel when the flag is on.
5. Preserve clip counters and `friction_source` write-back semantics.

## Validation Gate

1. 10m strict compare
2. 2h strict compare
3. 40h strict compare only if the first two pass
4. Accept only if 40h `evolve/model time < 47.05382442474365 s`
