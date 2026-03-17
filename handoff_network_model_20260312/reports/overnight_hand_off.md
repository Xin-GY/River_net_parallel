# Overnight Hand-Off

## Branch State

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- source accepted checkpoint: `689ae0b`
- source branch: `feature/cpp-exact-accepted-after-global-cfl`

## What Landed

This branch re-runs the assemble deep ownership push on top of the accepted global-CFL baseline, rather than using the older preserved prototype as a benchmark reference.

Landed code path:

- `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`

## Outcome

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h compare: `allclose = true`

Performance:

- accepted source gate: `60.74310255050659 s`
- new candidate: `47.05382442474365 s`

## Why It Works

- the deep assemble kernel now owns conservative flux increment, Manning post-step, conservative dry admissibility, and stage-local write-back
- the old global-CFL ownership bottleneck is already removed in the source baseline
- the local assemble reduction survives end-to-end on the new baseline

## What Did Not Change

- no refresh-deep logic
- no residual/Jacobian reopening
- no fullstep/dispatch reshaping
- no external-boundary-deep code
- no threaded implementation

## Suggested Next Round

1. treat this branch as the new accepted exact candidate
2. only then re-audit the new Top 1 blocker on top of this branch
3. if deterministic C++ threads are explored later, start with assemble, not global CFL
