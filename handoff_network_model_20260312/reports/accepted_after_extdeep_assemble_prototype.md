# Assemble Deep Prototype Preservation

This branch preserves an exact `Assemble_Flux_2` ownership prototype started after the
external-boundary-deep re-audit.

## Status

- branch: `feature/cpp-exact-accepted-after-extdeep-assemble`
- source accepted exact checkpoint:
  - `9a7c094` `perf: deepen exact rectangular Roe flux ownership (+28.6% 40h evolve)`
- current branch state: **prototype only**

## What this prototype tries to do

- push `Assemble_Flux_2` deeper into native ownership
- combine:
  - conservative flux increment
  - exact Manning post-step
  - conservative dry admissibility
  into a more native-owned exact post-flux chain

## Why it is not accepted

At the time of preservation:

- this prototype had not passed the full acceptance gate
- short-case replay exposed bridge-hit / validation ambiguity that required further audit
- there is no accepted 40h exact result attached to this branch state yet

So this branch is being preserved for later exact audit, not promoted as a new baseline.

## Commit policy for this preservation

- keep source edits and this report
- do **not** include generated extensions, benchmark JSON, compare JSON, cProfile output, or result folders

## How to use it later

Use this branch only as:

- a prototype reference
- a starting point for a fresh accepted exact re-audit of `Assemble_Flux_2`

Do not treat it as a benchmark reference until strict compare and 40h net-gain checks are rerun cleanly.
