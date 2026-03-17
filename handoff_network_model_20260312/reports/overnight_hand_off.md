# Overnight Hand-Off

## Branch

- branch: `feature/cpp-exact-after-assemble-threads-v1`
- source accepted candidate: `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2@445c2c9`

## What This Round Did

- created a clean continuation worktree from `445c2c9`
- rebuilt the current accepted exact Cython/C++ modules on this branch
- re-ran 10m / 2h / 40h fresh accepted-path replays
- completed a dedicated feasibility audit for deterministic C++ native threads on deep assemble

## What This Round Did Not Do

- no threading implementation
- no changes to nodechain
- no changes to global CFL
- no refresh/fullstep/external-boundary variants
- no build-flag experiments

## Key Finding

Deep assemble is still the most thread-shaped stage in the current accepted exact path, but it is now too fine-grained to be a high-confidence first threading target:

- `river_step.assemble = 2.831578 s` on fresh 40h replay
- `river_step.assemble.calls = 29783`
- average stage cost per step is about `95 us`
- largest river has only `36` cells
- total cells across the network is `293`

The likely first useful threading design would need coarser cross-river batching or a persistent worker model, which is outside this round's scope.

## Recommended Next State

- accepted exact candidate remains `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2@445c2c9`
- this branch should be treated as a threads-feasibility no-go checkpoint unless a later round explicitly authorizes a coarser deterministic threading design
