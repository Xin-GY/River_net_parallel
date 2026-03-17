# Final CPP After GlobalCFL Assemble V2 Recommendation

## Verdict

This round **does** produce a new accepted exact candidate.

## New Candidate

- branch: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2`
- commit: pending checkpoint on top of `689ae0b`
- feature flag: `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`

## Acceptance Gate

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h compare: `allclose = true`

Performance:

- accepted source gate `689ae0b`: `60.74310255050659 s`
- new candidate: `47.05382442474365 s`

## Why It Passed This Time

The old preserved assemble prototype already showed that deeper assemble ownership was exact and locally faster. It failed the old gate because:

- nodechain / boundary shells still dominated
- global CFL had not yet been pushed down

After `689ae0b` accepted the global-CFL serial native path, that blocker was removed. Reapplying the assemble pushdown on top of the new baseline now yields a net exact win at 40h scale.

## Current Remaining First-Order Blocker

Raw Top 1 cost still remains:

- `boundary_updater / nodechain`

But the remaining obvious deeper routes there are still close to the rejected refresh/fullstep family, so the next move should only reopen nodechain if a materially different ownership idea appears.

## Threads Recheck

Do not implement threads in this round.

If a later round explicitly evaluates deterministic C++ threading, `Assemble_Flux_2` is now a better first candidate than `global_CFL`, because:

- it still keeps `2.428812 s` of 40h cost
- it is now much more native-owned
- it is cell-local and naturally partitionable

## Recommendation

Upgrade this branch to the new accepted exact candidate and continue future exact-only work from here, not from `689ae0b`.
