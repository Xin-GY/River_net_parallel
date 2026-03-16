# cpp fullchain branch layout

- source accepted branch: `feature/cpp-exact-evolve-kernelize-next`
- source accepted head: `a67a12e`
- new working branch: `feature/cpp-exact-evolve-fullchain-pushdown`
- current worktree: `/home/xin/River_net_parallel`
- preserved source worktree: `/tmp/feature_cpp_exact_evolve_kernelize_next`

## code kept
- accepted phase-3 exact config wiring
- current Cython nodechain direct-fast path
- current Cython Roe flux path
- current C++ evolve bridge and output buffer
- all Python/Cython fallback paths and feature flags

## explicitly excluded from commit scope
- source worktree compile artifacts (`*.so`, generated `*.c`, generated `*.cpp`)
- old benchmark intermediate json/prof files
- rejected direct-dispatch bridge path as default behavior
- multiprocess/thread benchmark outputs
- FAST_MODE and any approximate solver path

## branch intent
- continue from the accepted exact semantics only
- push remaining evolve hot loops and state commit deeper into C++
- benchmark only single-process exact evolve/model time
