# Final Recommendation: C++ River Threads V2 Clean

## Recommendation

Do not upgrade this branch into a new accepted exact candidate.

## Why

This round succeeds in one important way and fails in the other required way:

1. it restores exactness for the threaded path
2. it does not produce a real speedup

The restored exactness is meaningful. Unlike the earlier v1 prototype, the new native stage-barrier path passes 10m strict compare for all tested thread counts `1 / 2 / 4 / 8 / 14`.

The speed gate, however, is not met. On the same 10m harness:

- serial: `4.83 s`
- threaded-1: `5.02 s`
- threaded-2: `4.99 s`
- threaded-4: `5.20 s`
- threaded-8: `4.99 s`
- threaded-14: `4.91 s`

The best threaded result is still slower than serial. Therefore this branch does not qualify for 2h or 40h escalation under the agreed gate.

## Current Accepted Baseline

The accepted exact baseline remains:

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: `c92a3ca`
- 40h exact evolve/model time: `34.26593613624573 s`

## What This Branch Should Be Treated As

Preserve this branch as:

- deterministic exact C++ threaded prototype
- useful evidence that the earlier drift can be repaired
- below speed gate

It is not a new accepted result.

## Root Cause Summary

The main numerical issue in v1 was not an unavoidable threading instability. It was a code-path mismatch, especially in CFL ownership. V2 repaired that mismatch and recovered exactness. The remaining problem is granularity and overhead:

- worker synchronization still costs more than it saves on this network
- river-local stages are now exact, but not large enough to amortize stage barriers and worker wakeups
- nodechain and boundary remain the dominant raw costs, but they are still not safe first thread targets under the current exact constraints

## Final Decision

- 10m strict compare: pass for `1 / 2 / 4 / 8 / 14`
- 2h strict compare: not run
- 40h strict compare: not run
- new accepted candidate: no
- recommended next action: preserve as prototype and stop this thread line here
