# Nodecommit Refresh WIP Preservation

This branch preserves dirty continuation work that existed on top of the accepted
`feature/cpp-exact-evolve-nodecommit-refresh` checkpoint.

## Status

- branch: `feature/cpp-exact-evolve-nodecommit-refresh-wip`
- accepted source checkpoint remains:
  - `9535623` `perf: deepen exact nodechain commit ownership (+0.8% 40h evolve)`
- this WIP branch is **not** an accepted exact candidate

## What is being preserved

- code changes and tooling updates that were present in the dirty worktree
- branch-local continuation context for later replay or audit
- markdown context that explains where this branch sat in the larger exact C++ family

## Why this exists

`9535623` is still a meaningful accepted checkpoint in the family and should not be
polluted by unreviewed continuation work. This branch keeps the uncommitted state
available for GitHub/GPT analysis without changing the accepted branch head.

## Commit policy for this preservation

- keep source edits and key markdown context
- exclude generated Cython/C++ outputs, benchmark JSON, result directories, and local artifacts

## Interpretation

Treat this branch as a preserved continuation snapshot:

- useful for reconstruction and later comparison
- not accepted
- not the branch to benchmark against directly
