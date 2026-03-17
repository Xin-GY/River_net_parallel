# Overnight Hand-off

## Branches / worktrees

- preserved experiment worktree:
  - `/tmp/feature_cpp_exact_evolve_nodecommit_refresh`
  - contains the rejected refresh-deep experiment and its diff snapshot
- clean continuation worktree:
  - `/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next`
  - branch: `feature/cpp-exact-evolve-nodecommit-refresh-next`
  - starts from accepted checkpoint `9535623`

## Accepted code state

Best accepted exact checkpoint remains:

- `9535623` `perf: deepen exact nodechain commit ownership (+0.8% 40h evolve)`

Accepted exact 40h evolve/model time:

- `91.32992911338806 s`

## What this continuation branch added

- explicit no-go documentation for:
  - refresh-deep experiments
  - residual/Jacobian recheck
  - fullstep recheck
- opt-in build flag support for:
  - `ISLAM_BUILD_USE_NDEBUG`
  - `ISLAM_BUILD_USE_MARCH_NATIVE`
- explicit rejection evidence for `-march=native` on the exact path

## What is experimental only

- inline Cython refresh-deep implementation:
  - fast
  - not exact
- single-cell C++ exact refresh:
  - exact on 10m/2h
  - slower than accepted path
- `-march=native` build:
  - not exact
  - rejected

## Key report paths

- refresh-deep plan:
  - [cpp_nodechain_refresh_deep_plan.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/cpp_nodechain_refresh_deep_plan.md)
- refresh-deep implementation notes:
  - [cpp_nodechain_refresh_deep_impl.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/cpp_nodechain_refresh_deep_impl.md)
- refresh-deep before/after:
  - [cpp_nodechain_refresh_deep_before_after.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/cpp_nodechain_refresh_deep_before_after.md)
- residual recheck:
  - [nodechain_residual_recheck_after_commit_refresh.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/nodechain_residual_recheck_after_commit_refresh.md)
- fullstep recheck:
  - [fullstep_recheck_after_nodecommit_refresh.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/fullstep_recheck_after_nodecommit_refresh.md)
- build flags evaluation:
  - [cpp_build_flags_eval_v3.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/cpp_build_flags_eval_v3.md)
- final recommendation:
  - [final_cpp_nodecommit_refresh_recommendation.md](/tmp/feature_cpp_exact_evolve_nodecommit_refresh_next/handoff_network_model_20260312/reports/final_cpp_nodecommit_refresh_recommendation.md)

## Recommended next move

Do not keep digging on this branch family blindly.

If we continue exact-only work, the next step should come from a fresh hotspot audit on the still-accepted exact path, not from extending any of the rejected refresh/fullstep/build-flag experiments recorded here.
