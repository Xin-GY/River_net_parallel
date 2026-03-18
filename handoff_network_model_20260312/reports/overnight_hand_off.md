# Overnight Hand-Off

## Branch State

- branch: `feature/cpp-exact-after-assemble-boundary-shell-v1`
- source accepted baseline: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2@445c2c9`
- current docs on `main` are stale; use `445c2c9` as the real accepted baseline for this family

## What Landed

Landed behind feature flag:

- `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP=1`

Implemented scope:

- precompiled external boundary op plan
- prebound fixed-order routing/dispatch shell
- Cython serial executor for the external boundary plan
- optional callable metadata plumbing

Not changed:

- accepted inflow/outflow formulas
- float64 semantics
- nodechain numeric ownership
- external-boundary-deep formulas
- threads

## Validation Outcome

### Final exact candidate

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h compare: `allclose = true`

Same-harness 40h replay:

- baseline: `43.93435072898865 s`
- final exact candidate: `44.53874897956848 s`

Verdict:

- exact: yes
- faster than same-harness baseline: no
- promote to accepted: no

### Rejected grouped attempt

The first grouped-evaluator shell version was:

- faster
- exact on 10m / 2h
- not exact on 40h

It is rejected.

## Recommended Interpretation

This branch is useful because it proves:

- the boundary routing shell can be deepened without changing formulas
- the grouped evaluator optimization is the exact-risky part
- shell-only deepening is not enough to justify promotion once grouped batching is removed

## Suggested Next Round

1. keep `445c2c9` as the latest accepted exact candidate
2. keep this branch as a preserved exact prototype / no-go evidence line
3. do not reopen grouped evaluator batching unless there is a new exact-safe design
4. re-audit the remaining Top 1 blocker before choosing any new implementation target
