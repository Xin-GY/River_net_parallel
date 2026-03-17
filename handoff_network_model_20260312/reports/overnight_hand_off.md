# Overnight Hand Off

## Branch

- branch: `feature/cpp-exact-accepted-after-global-cfl`
- start checkpoint: `feature/cpp-exact-accepted-reaudit-next@9a7c094`
- new accepted commit candidate from this round: pending current branch head

## What this round did

- created a clean continuation branch from `9a7c094`
- reran the accepted exact path on 10m / 2h / 40h to recheck the current ownership gap
- confirmed `global CFL / dt reduction` was still the highest-confidence next move outside the rejected nodechain-tail family
- implemented a serial native deep path behind:
  - `ISLAM_CPP_USE_GLOBAL_CFL_DEEP=1`
- validated it on:
  - 10m
  - 2h
  - 40h

## Result

The new serial native global-CFL path is:

- exact
- faster than the accepted baseline

40h exact result:

- accepted historical baseline: `65.23701047897339 s`
- new candidate: `60.74310255050659 s`

## Exactness

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- `cfl_history.csv`: exact, same row count, no `global_dt` diff
- `internal_node_history.csv`: exact, same row count

## What was deliberately not done

- no Python-level multi-process / multi-thread benchmark
- no FAST_MODE
- no approximation
- no refresh-deep reopen
- no residual / Jacobian deep reopen
- no fullstep / dispatch reshape
- no external-boundary-deep logic
- no `-march=native`

## Threading status

This branch does **not** upgrade to a threaded accepted path.

Reason:

- serial native already reduced `dt_update.global_cfl` to `0.728253 s`
- the stage is no longer large enough to justify a deterministic thread experiment inside the same round

## Recommended next step

- treat this serial global-CFL deep path as the new accepted exact checkpoint for the branch family
- if exact-only work continues, do a fresh audit from this new baseline before choosing the next single point
- likely next point:
  - `Assemble_Flux_2` deeper ownership re-audit on top of the new baseline
  - unless a materially new, non-refresh-like nodechain ownership route is found
