# cpp nodecommit refresh branch layout

- source accepted branch: `feature/cpp-exact-evolve-nodechain-deepnative`
- source accepted commit: `f8f0db0`
- new continuation branch: `feature/cpp-exact-evolve-nodecommit-refresh`
- worktree path: `/tmp/feature_cpp_exact_evolve_nodecommit_refresh`

Accepted exact config carried into this branch:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

This branch will keep:

- single-process exact evolve path
- current native nodechain deep-apply ownership
- current deep Roe flux ownership
- current native `Update_cell_proprity2` / `Assemble_Flux_2` / `Roe_matrix` / `Face_U_C` exact kernels

This branch explicitly excludes:

- multiprocessing / multithreading benchmark work
- FAST_MODE and any approximate solver logic
- new bridge dispatch-shape experiments
- generated `.so`, generated `.c/.cpp`, benchmark JSON, and result directories from commits

