# Fullchain Pushdown WIP Preservation

This branch preserves branch-local work that was left dirty on top of the accepted
`feature/cpp-exact-evolve-fullchain-pushdown` checkpoint.

## Status

- branch: `feature/cpp-exact-evolve-fullchain-pushdown-wip`
- accepted source checkpoint remains:
  - `1d71dee` `perf: nativeize update-cell exact kernel (+12.2% 40h evolve)`
- this WIP branch is **not** an accepted exact baseline

## What is being preserved

- in-progress exact C++ ownership push for the river-step post-flux / update chain
- branch-local code edits that were not yet cleanly checkpointed
- a preserved progress log so later analysis can see what was being attempted

## Why this exists

The accepted checkpoint on this line should stay clean and reproducible. The dirty
continuation work is still useful for later analysis, but it should live on its own
WIP branch instead of hanging off the accepted branch head.

## Commit policy for this preservation

- keep source edits
- keep concise markdown context
- do **not** include generated extensions, benchmark JSON, result folders, or local build artifacts

## Interpretation

Treat this branch as:

- useful implementation context
- not accepted
- not a benchmark reference
- a possible starting point for a future exact continuation if someone wants to resume this line
