# Threads Recheck After Source V1

## Decision

Do not enter any C++ threads implementation yet.

## Why

After `source_deep_v1`:

- `source` is reduced to `0.329018 s` on the fresh 40h replay
- `assemble` remains only `1.597568 s`
- `global_CFL` was already accepted as small earlier

The remaining raw heavy costs are still:

- `nodechain.total`
- `boundary_updater.total`

Those are not good first thread targets right now because the obvious routes are still tightly coupled to already-rejected exact families:

- refresh deep
- fullstep / dispatch reshaping
- boundary grouped-evaluator batching

## Best Current Threads Answer

- first deterministic C++ threads object: **none**
- recommendation: **do not implement threads in the next round unless a materially different exact ownership design appears first**
