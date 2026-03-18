# Final CPP After Source V1 Recommendation

## Verdict

This round **does** produce a new accepted exact candidate.

## New Candidate

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: pending final checkpoint on top of `348aadc`
- feature flag: `ISLAM_CPP_USE_SOURCE_DEEP=1`

## Acceptance Gate

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h compare: `allclose = true`

Performance:

- previous accepted 40h gate `445c2c9`: `47.05382442474365 s`
- new candidate 40h: `34.26593613624573 s`

## Why It Passed

`Caculate_source_term_2` remained almost fully Python-owned on the accepted baseline:

- Python per-interface loop
- Python left/right section lookup
- Python DEB table dispatch
- Python friction-source assembly

This round moved that ownership into a serial native path without changing:

- formulas
- float64 semantics
- traversal order
- clip / epsilon / guard order

The source-stage win is large enough to survive the full 40h gate rather than disappearing into harness noise.

## Current Remaining First-Order Blocker

Raw Top 1 remains:

- `nodechain.total`
- `boundary_updater.total`

But the remaining obvious deeper routes there are still too close to already-rejected exact families, so the next move should not be a blind continuation there.

## Threads Decision

Do not implement threads now.

After this round:

- `source` is too small to justify first-thread effort
- `assemble` is also smaller than before
- the large remaining stages are still the risky nodechain / boundary families

## Recommendation

Upgrade this branch to the new accepted exact candidate and continue future exact-only work from here, not from `445c2c9`.
