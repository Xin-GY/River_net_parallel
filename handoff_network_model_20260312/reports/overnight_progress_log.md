# Overnight Progress Log

## 2026-03-17

- created `feature/cpp-exact-after-globalcfl-assemble-reaudit-v2` from accepted exact candidate `689ae0b`
- created clean worktree at `/tmp/feature_cpp_exact_after_globalcfl_assemble_reaudit_v2`
- recorded preflight git status and branch layout
- rebuilt Cython/C++ extensions in the new worktree
- replayed accepted exact config for 10m, 2h, and 40h
- verified strict compare passes against `/tmp/feature_cpp_exact_accepted_after_global_cfl` outputs for all three cases
- wrote `accepted_after_globalcfl_assemble_v2_hotspot_recheck.md`
- conclusion from the fresh audit: `Assemble_Flux_2` remains the single highest-confidence next move on top of `689ae0b`
- ported assemble deep ownership logic from the preserved prototype into the `689ae0b` baseline without mixing refresh/fullstep/external-boundary paths
- rebuilt Cython/C++ river kernels
- ran `assemble_deep_v2` exact gate for 10m / 2h / 40h
- strict compare passed for all three cases
- 40h model time improved from `50.941080 s` fresh replay / `60.743103 s` historical accepted gate to `47.053824 s`
- threads were rechecked conceptually only; no threaded implementation was added in this round
