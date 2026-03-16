## Branch layout

- source accepted commit: `d26ea2a850caa210961130019adad5d7c7ab12b5`
- source branch: `feature/cpp-exact-evolve-flux-residual-fullstep`
- new branch: `feature/cpp-exact-evolve-nodechain-deepnative`
- worktree path: `/tmp/feature_cpp_exact_evolve_nodechain_deepnative`

## Accepted exact configuration carried forward

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`

## Included source baseline

- accepted exact nodechain prebound fast path
- accepted Roe flux deep ownership path
- accepted C++ face-uc / roe-matrix / update-cell / assemble kernels
- existing Python and Cython fallbacks

## Explicit exclusions from commits

- generated extension artifacts:
  - `cython_node_iteration.c`
  - `cython_node_iteration*.so`
  - `cython_river_kernels.cpp`
  - `cython_river_kernels*.so`
- benchmark JSON summaries and compare outputs
- temporary result directories used only for validation

## Scope of this branch

This branch only pushes deeper native ownership into nodechain:

1. `apply_and_boundary_closure`
2. residual / `Ac` / stopping
3. final apply / state commit

It does not reopen:

- FAST paths
- dispatch-shape experiments
- multiprocessing or multithreading benchmarks
- initialization optimization
