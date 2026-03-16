# cpp branch state summary

## accepted source line

- source branch: `feature/cpp-exact-evolve-kernelize-next`
- source frozen worktree: `/tmp/feature_cpp_exact_evolve_kernelize_next`
- accepted head: `a67a12e`

### accepted exact config from phase-3 source line

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

## current pushdown continuation line

- current branch: `feature/cpp-exact-evolve-fullchain-pushdown-next`
- current worktree: `/tmp/feature_cpp_exact_evolve_fullchain_pushdown_next`
- continuation start point: `1d71dee`

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
2. even after wrapper-bypass and native update-cell, nodechain post-iteration state commit still retains substantial Python ownership
3. `Assemble_Flux_2` remains the clearest remaining per-cell native gap after `Update_cell_proprity2`
4. generated compile artifacts and benchmark JSONs exist in both worktrees and must stay out of source commits

## current continuation working baseline

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

Validated no-profile spot checks in this clean continuation worktree:

- 10m:
  - `1.266910 s`
- 2h:
  - `9.865382 s`

## next optimization direction

1. push `Assemble_Flux_2` and related per-cell conservative/friction/admissibility loops deeper into C++
2. native-ize nodechain state commit and post-node write-back
3. revisit remaining river-step kernels in current hotspot order:
   - `Caculate_Roe_Flux_2`
   - `Caculate_Roe_matrix`
   - `Caculate_face_U_C`
4. only after the above, revisit a fuller native full-step loop

## branch-local accepted delta vs phase-3 source baseline

On this pushdown branch, the newly validated exact addition is:

- `ISLAM_CPP_USE_UPDATE_CELL=1`

Validated exact results relative to the phase-3 accepted source config:

- 10m:
  - `1.457326 s -> 1.259714 s`
- 2h:
  - `11.400661 s -> 10.262386 s`
- 40h:
  - `202.210932 s -> 177.525983 s`

All three validation windows pass exact compare.

## commit policy for this line

- safe docs/profiling checkpoints are allowed when they do not change exact semantics
- experimental kernels stay behind feature flags until:
  - 10m exact compare passes
  - 2h exact compare passes
  - 40h exact compare passes
  - 40h evolve/model improves over `202.210932 s`
