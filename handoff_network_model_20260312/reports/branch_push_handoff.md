# Branch Push Handoff

This file explains how to interpret the branches once they are pushed to GitHub.

## What is accepted right now

- Best accepted exact branch:
  - `feature/cpp-exact-accepted-reaudit-next`
  - commit `9a7c094`
  - 40h exact `evolve/model time = 65.23701047897339 s`
  - strict compare passes on 10m / 2h / 40h
- Best FAST branch:
  - `fast-mode-30s`
  - faster wall-clock, but approximate and not exact-equivalent

## What the branch family progression means

The exact C++ family progressed roughly as:

1. `feature/cython-exact-nodechain-top3`
2. `feature/cpp-exact-evolve-fullchain`
3. `feature/cpp-exact-evolve-fullchain-pushdown-next`
4. `feature/cpp-exact-evolve-nodechain-deepnative`
5. `feature/cpp-exact-evolve-nodecommit-refresh`
6. `feature/cpp-exact-accepted-reaudit-next`

Key accepted milestones:

- `9535623`: nodechain commit deep accepted
- `9a7c094`: rectangular Roe flux deep accepted

## What the no-go and WIP branches mean

- `feature/cpp-exact-accepted-reaudit-after-rectflux`
  - preserves the exact no-go evidence for external-boundary-deep
  - useful because it proves the drift is not in interpolation math
- `feature/cpp-exact-accepted-after-extdeep-assemble`
  - preserves a prototype for deeper `Assemble_Flux_2` ownership
  - not accepted, not benchmark reference, but worth future audit
- `feature/cpp-exact-evolve-nodecommit-refresh-wip`
  - preserved dirty continuation state from the `9535623` line
- `feature/cpp-exact-evolve-fullchain-pushdown-wip`
  - preserved dirty continuation state from the `1d71dee` line

## Recommended next exact-only direction

If exact optimization resumes, start from:

- `feature/cpp-exact-accepted-reaudit-next@9a7c094`

High-confidence next blocker:

- `Assemble_Flux_2` deeper ownership pushdown

Do not restart:

- external-boundary-deep exact in its current form
- refresh deep old variants
- residual/Jacobian deep as a primary path
- fullstep/dispatch reshaping
- build-flag experiments like `-march=native`

## Push advice

- Push accepted branches first so GitHub has stable references.
- Push WIP/no-go branches next so GPT can inspect failure evidence and branch-local context.
- Push archival branches last; they are preservation-only and not part of the current recommendation.
