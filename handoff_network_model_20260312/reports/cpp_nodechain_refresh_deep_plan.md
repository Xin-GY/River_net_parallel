# C++ Nodechain Refresh Deep Plan

## Goal

Push the remaining `_refresh_cell_state` ownership in the exact nodechain tail deeper into native code, after the accepted `9535623` deep-commit checkpoint.

The intended target was the closure-to-commit tail:

- closure result already lives in native-owned boundary-face state
- `_refresh_cell_state` still runs through Python-owned river state
- final apply / commit then consumes the refreshed state

The plan was to remove the remaining Python-owned refresh work without changing:

- exact formulas
- update order
- float64 semantics
- final committed river/boundary state

## Candidate implementations

### Candidate A: Cython-native refresh

Inline the refresh logic inside `cython_node_iteration.pyx` and keep the full closure-to-refresh tail inside the Cython/native loop.

Expected upside:

- eliminate Python callback-style refresh
- minimize Python-owned intermediate state churn
- reduce nodechain tail crossings further

Risk:

- refresh logic is tightly coupled to accepted Python update ordering
- even small differences in refresh ordering can perturb CFL history and step schedule

### Candidate B: Single-cell C++ exact refresh kernel

Keep the accepted nodechain flow, but replace the refresh body with a conservative C++ exact single-cell kernel called from the deep nodechain plan.

Expected upside:

- preserve exact formulas more explicitly than Candidate A
- reduce Python work in the refresh tail

Risk:

- per-cell native call overhead can dominate if ownership is still fragmented
- compiling the surrounding `cython_node_iteration` layer as C++ may itself increase overhead on this branch

## Acceptance rule

The refresh-deep path can only be accepted if all of the following hold:

- 10m strict compare passes
- 2h strict compare passes
- 40h strict compare passes
- 40h `evolve/model time` is better than the accepted `9535623` baseline

If either candidate fails exactness or slows down the accepted path, it remains a rejected experiment behind a flag only.
