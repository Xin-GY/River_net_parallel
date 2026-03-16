# cpp fullchain branch layout

## source and continuation

- source branch with protected dirty experiment state: `feature/cpp-exact-evolve-fullchain-pushdown`
- source worktree: `/home/xin/River_net_parallel`
- source accepted head: `1d71dee`
- source dirty state kept in place:
  - unaccepted `Assemble_Flux_2` native pushdown prototype
  - local benchmark json/prof artifacts
  - generated extension outputs
- continuation branch: `feature/cpp-exact-evolve-fullchain-pushdown-next`
- continuation worktree: `/tmp/feature_cpp_exact_evolve_fullchain_pushdown_next`
- continuation start commit: `1d71dee`

## accepted exact baseline carried into this branch

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=0`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- accepted evolve/model baselines:
  - 10m: `1.457326 s`
  - 2h: `11.400661 s`
  - 40h: `202.210932 s`

## code intentionally kept

- accepted phase-3 exact bridge/runtime wiring
- accepted nodechain wrapper-bypass path
- accepted Cython Roe flux path
- accepted C++ update-cell exact kernel and its feature flag
- all Python/Cython/C++ fallback paths needed for exact bisection

## explicitly excluded from commit scope

- source worktree compile artifacts (`*.so`, generated `*.c`, generated `*.cpp`)
- source benchmark intermediate json/prof files
- unaccepted `Assemble_Flux_2` native prototype from the source worktree
- rejected direct-dispatch bridge path as default behavior
- any multiprocess/thread benchmark outputs
- FAST_MODE and any approximate solver path

## branch intent

- keep the source dirty worktree recoverable without any destructive cleanup
- continue all new work from a clean child worktree at the accepted `1d71dee` baseline
- profile only single-process exact `evolve/model time`
- push the remaining Python/Cython numeric chain, state commit, and per-cell/per-face hot loops deeper into C++
