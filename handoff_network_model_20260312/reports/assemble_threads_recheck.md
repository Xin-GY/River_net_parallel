# Assemble Threads Recheck

## Verdict

Do not implement assemble threads in this round, but it is now the first credible C++ native-threads candidate if a later round explicitly targets deterministic threading.

## Why It Is Worth Rechecking

- `Assemble_Flux_2` is now much more native-owned than before
- the remaining 40h stage cost is still material: `river_step.assemble = 2.428812 s`
- work is per-cell and naturally partitionable by contiguous cell ranges
- the stage has no global floating-point reduction requirement inside the deep kernel itself

## Why Not Implement Threads Now

- this round already produced a clean accepted serial exact gain
- the user asked for serial first and threads only as a later recheck
- the next priority should remain stabilizing the new accepted serial baseline before widening the search space

## If Threads Are Tried Later

Preferred first trial shape:

- fixed contiguous cell chunks per thread
- thread-local scratch only
- disjoint writes to `Flux`, `S`, and `Q`
- no dynamic scheduling
- no unordered floating-point reduction
- no change to cell update order inside each chunk

Recommended first implementation target:

- the deep assemble kernel only

Not recommended as first threaded target:

- nodechain
- global CFL
- any stage that introduces ordered reductions or cross-river coordination
