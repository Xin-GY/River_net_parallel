# cpp branch state summary

## accepted source line

- source branch: `feature/cpp-exact-evolve-kernelize-next`
- source frozen worktree: `/tmp/feature_cpp_exact_evolve_kernelize_next`
- accepted head: `a67a12e`

### accepted exact config

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=0`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

### accepted exact evolve/model results

- 10m: `1.457326 s`
- 2h: `11.400661 s`
- 40h: `202.210932 s`

### accepted conclusions

- current exact gains come from:
  - nodechain wrapper-bypass
  - existing Cython nodechain direct-fast path
  - existing Cython Roe-flux path
- direct-dispatch bridge is documented but rejected:
  - short cases improved
  - 40h full case regressed
- `Update_cell_proprity2` native variants are still excluded from accepted exact config

## current pushdown line

- current branch: `feature/cpp-exact-evolve-fullchain-pushdown`
- current worktree: `/home/xin/River_net_parallel`
- start point for this line: `a67a12e`

### this line's purpose

- keep accepted phase-3 exact semantics unchanged
- continue pushing remaining `evolve` compute/state chains deeper into C++
- benchmark only single-process exact `evolve/model time`
- exclude:
  - multiprocess/thread benchmark routes
  - FAST_MODE
  - response table
  - q-hint / approximate node solve
  - initialization-time optimization

## currently documented on this line

- preflight and branch layout:
  - `cpp_fullchain_preflight_git_status.txt`
  - `cpp_fullchain_untracked_inventory.md`
  - `cpp_fullchain_branch_layout.md`
- remaining native-gap reports:
  - `evolve_remaining_python_chain.md`
  - `evolve_native_gap_topdown.md`
  - `evolve_remaining_hotspots_top10.md`

## current known problems

1. bridge-only gains are small because the time-step loop still crosses Python/Cython/C++ boundaries heavily
2. `Update_cell_proprity2` is still the clearest remaining native gap, but prior native variants have shown an unresolved exact gap versus the Python reference path
3. `Assemble_Flux_2` and nodechain post-iteration state commit still retain substantial Python ownership
4. generated compile artifacts and benchmark JSONs exist in both worktrees and must stay out of source commits

## next optimization direction

1. isolate and fix the exact rounding/commit gap in `Update_cell_proprity2`
2. push `Assemble_Flux_2` and related per-cell conservative/friction/admissibility loops deeper into C++
3. native-ize nodechain state commit and post-node write-back
4. only after the above, revisit a fuller native full-step loop

## commit policy for this line

- safe docs/profiling checkpoints are allowed when they do not change exact semantics
- experimental kernels stay behind feature flags until:
  - 10m exact compare passes
  - 2h exact compare passes
  - 40h exact compare passes
  - 40h evolve/model improves over `202.210932 s`
