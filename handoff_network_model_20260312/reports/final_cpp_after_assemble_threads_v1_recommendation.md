# Final CPP After Assemble Threads V1 Recommendation

## Verdict

Do **not** implement deterministic C++ native threads for deep assemble on top of `445c2c9` in this round.

This branch stops after the feasibility audit because the kernel is thread-friendly in structure but too small in actual per-step grain size to be a high-confidence first threading target.

## Why The Trial Stops At Phase 1

- `river_step.assemble` is only `2.831578 s` over the full 40h replay
- the stage runs `29783` times
- average assemble stage cost is only about `95 us` per global step
- the largest river has only `36` cells, with `293` cells total across the whole network

The deep assemble kernel is already native-owned enough that the remaining cost is mostly **small repeated work**, not a big coarse-grained chunk waiting to be parallelized safely.

A first deterministic-threading implementation here would likely be dominated by:

- worker wakeup / join overhead
- chunk management
- cache and synchronization overhead

before it can recover any of the remaining `2.831578 s`.

## Current Remaining First-Order Blocker

Raw Top 1 remains:

- `boundary_updater / nodechain`

But the obvious deeper routes there are still too close to the previously rejected:

- refresh-deep family
- residual / Jacobian deep family
- fullstep / dispatch reshaping family

So this round does **not** reopen nodechain either.

## Best Threads Candidate Status

Within the current accepted exact path:

- assemble is still the cleanest **shape** for threading
- but not yet a clean enough **grain size** target

If threading is revisited later, it should only happen after a new coarser design is justified explicitly. That would be a different task from “deep assemble kernel only” and should not be smuggled into the current exact line.

## Recommendation

- keep `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2@445c2c9` as the current accepted exact candidate
- keep this branch as a documentation-only continuation of the threads feasibility audit
- do not spend the next round on assemble threads unless a materially coarser deterministic design is approved first
