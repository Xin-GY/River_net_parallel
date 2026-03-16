# Overnight Progress Log

## 2026-03-16 C++ kernelize-next phase 1

### Done

- created clean continuation branch:
  - `feature/cpp-exact-evolve-kernelize-next`
- created isolated worktree:
  - `/tmp/feature_cpp_exact_evolve_kernelize_next`
- recorded preservation / branch-layout reports for the source bridge line
- mapped the current exact evolve chain again from the new branch’s actual code, not from older notes
- wrote C++-focused phase-1 reports:
  - `cpp_evolve_call_chain.md`
  - `cpp_nodechain_math_and_dataflow.md`
  - `cpp_riverstep_math_and_dataflow.md`
  - `cpp_data_layout_and_boundary_crossings.md`

### Findings

- the current bridge is real, but it is still mostly a compiled loop shell
- the exact nodechain remains object-heavy:
  - Cython shell
  - Python river objects
  - Python boundary-closure methods
  - Python-backed section-table lookups
- the network step still dispatches six river phases from Python via `call_river_function_by_name`
- the real blocker is now clear:
  - too many Python/Cython/C++ crossings
  - too much state still owned by Python objects
- this explains why 40h evolve improved by only about `0.84 s`

### Next

- establish the current branch’s single-process exact evolve-only baseline for:
  - 10m
  - 2h
  - 40h
- generate Top 10 hotspots and identify the real Top 3 on this branch
- then start the first true native kernelization step:
  - internal node exact chain in C++

## 2026-03-16 C++ kernelize-next phase 2

### Done

- rebuilt the missing local `cython_cross_section` extension in this worktree
- reran the single-process exact baseline after that rebuild for:
  - 10m
  - 2h
  - 40h
- added a branch-local profiling tool:
  - `tools/profile_cpp_exact_serial.py`
- added safe perf counters for:
  - boundary updater
  - nodechain sub-stages
  - river-step sub-stages
  - bridge crossing counts
- wrote corrected baseline and hotspot reports:
  - `cpp_exact_serial_baseline.md`
  - `cpp_hotspots_top10.md`

### Findings

- several early runs on this branch were invalid because the worktree was missing the compiled `cython_cross_section` extension
- after the rebuild, the corrected evolve-only baselines are:
  - 10m: `1.459050 s`
  - 2h: `12.330136 s`
  - 40h: `206.306033 s`
- the bridge-only line is therefore still effectively flat versus `835cf1f`
- corrected 2h profiling confirms the current Top 3 domains are:
  1. boundary updater / internal node chain
  2. Roe flux
  3. update cell
- the main reason bridge gains remain tiny is now explicit:
  - `14820` Python/Cython/C++ crossings in 2h
  - `336020` boundary-closure calls
  - `306380` width lookups inside nodechain residual/Ac work

### Next

- checkpoint the safe profiling/reporting infrastructure without mixing in the unvalidated direct-fast nodechain prototype
- then move to phase 3:
  - deeper native nodechain kernelization
  - first on 10m/2h exact compare
  - then on 40h evolve-only timing

## 2026-03-16 C++ kernelize-next phase 3

### Done

- tested a deeper direct stage-boundary numeric closure prototype inside `cython_node_iteration.pyx`
- rejected that prototype after a reproducible 10m segmentation fault
- tested direct table-ref width lookup inside nodechain residual/Ac assembly
- rejected that prototype after exact compare showed small but real drift
- implemented a safer exact wrapper-bypass nodechain path:
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - the nodechain loop now tries `river._stage_boundary_fix_level_cython_fast(...)` directly
  - if that fast exact closure rejects, the original Python wrapper path is preserved
- validated the accepted wrapper-bypass candidate on:
  - 10m
  - 2h
  - 40h

### Findings

- the two deeper prototypes were useful for scoping risk:
  - direct numeric closure was unstable
  - direct width-ref lookup was numerically non-exact
- the accepted wrapper-bypass cut stays exact and still gives a measurable full-case gain
- evolve/model time improved:
  - 10m: `1.459050 s -> 1.457326 s`
  - 2h: `12.330136 s -> 11.400661 s`
  - 40h: `206.306033 s -> 202.210932 s`
- corrected 2h perf also improved the nodechain shell:
  - `boundary_updater.total`: `4.076405 s -> 3.969430 s`
  - `nodechain.apply_and_boundary_closure`: `2.771246 s -> 2.681397 s`
  - `nodechain.final_apply`: `0.261257 s -> 0.253436 s`

### Next

- checkpoint the accepted wrapper-bypass nodechain implementation
- then continue to phase 5 style work:
  - reduce per-step Python/Cython/C++ boundary crossings
  - shrink the `call_river_function_by_name` fan-out inside the bridge loop

## 2026-03-16 C++ kernelize-next phase 5 experiment

### Done

- implemented a bridge-local direct-dispatch mode:
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=1`
- in that mode the bridge loop directly iterates cached `net._river_edges` for:
  - set-dt
  - face/U/C
  - Roe matrix
  - source
  - Roe flux
  - assemble
  - update cell
  - save-step result
  - CFL reduction
- fixed an exactness bug in the first draft:
  - direct CFL reduction must preserve the original object-valued `dti`
  - early `float(...)` coercion caused dt drift

### Findings

- after the dt fix, the direct-dispatch bridge is exact on:
  - 10m
  - 2h
  - 40h
- short-case gains were real:
  - 10m: `1.457326 s -> 1.452927 s`
  - 2h: `11.400661 s -> 11.254503 s`
- but the full case rejected it:
  - 40h: `202.210932 s -> 203.544599 s`
  - net result: `+1.333667 s`, slower than the accepted phase-3 path

### Next

- keep the direct-dispatch bridge as a documented rejected exact experiment
- return to the accepted phase-3 checkpoint for the branch code path
- continue future work from the better exact baseline:
  - nodechain wrapper-bypass accepted
  - bridge direct-dispatch rejected on full case

## 2026-03-16 C++ bridge checkpoint

- Added a new `Cython + C++` bridge layer for prepared evolve:
  - `cython_cpp_bridge.pyx`
  - `cpp/output_buffer.hpp/.cpp`
  - `cpp/evolve_core.hpp/.cpp`
  - `build_cpp_exact_kernels.py`
- Wired `Rivernet` so prepared evolve can route through:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0/1`
- Added a C++ output buffer path in `river_for_net.py` so the runtime can accumulate snapshots in native storage and only materialize them back into Python/xarray at finalize time.
- Updated `Islam.run_prepared_evolve(...)` so the evolve-only benchmark path actually exercises the new bridge.
- Found and fixed a long-run exactness issue:
  - the first bridge draft cast step-time scalars through `float(...)` each loop
  - this produced small 2-hour drift
  - the bridge now preserves the original Python-object arithmetic order for time-step updates and CFL/yield-step checks
- Validation status:
  - 10-minute exact compare: pass
  - 2-hour exact compare: pass
  - 40-hour exact compare against same-branch exact serial: pass
- Current measured evolve-only speed:
  - `40h cython exact serial`: `206.436461 s`
  - `40h cpp bridge`: `205.593739 s`
  - delta: `-0.842722 s`
- Next step:
  - move real numerical work, not only orchestration, from Python/Cython into C++ runtime kernels
  - start with the node iteration chain and then the river-step kernels

## 2026-03-16 C++ fullchain pushdown continuation

### Done

- created a clean continuation branch from the accepted update-cell checkpoint:
  - `feature/cpp-exact-evolve-fullchain-pushdown-next`
- recorded current preflight and native-gap reports for this continuation line
- implemented an exact native `Assemble_Flux_2` post-step kernel behind:
  - `ISLAM_CPP_USE_ASSEMBLE=1`
- moved the remaining explicit manning friction substep and explicit admissibility post-pass out of the Python per-cell loop and into C++:
  - `cpp/river_kernels.hpp`
  - `cpp/river_kernels.cpp`
  - `cython_river_kernels.pyx`
  - `river_for_net.py`
- diagnosed and fixed the original drift with step-by-step river/cell comparison scripts until:
  - 10m exact compare passed
  - 2h exact compare passed
  - 40h exact compare passed

### Findings

- the first native `Assemble_Flux_2` prototype failed not because of high-level orchestration, but because the friction coefficient path did not exactly match NumPy scalar semantics
- the accepted exact kernel now preserves the required staging for:
  - `g * DT * S`
  - `deb * deb`
  - float32/float64 interaction in the coefficient calculation
- after `Update_cell_proprity2` and `Assemble_Flux_2` are both native, the remaining fullchain gaps become much clearer:
  - nodechain state commit / final apply
  - deeper `Caculate_Roe_Flux_2` pushdown
  - `Caculate_Roe_matrix`, then `Caculate_face_U_C`

### Results

- current accepted continuation exact config:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - `ISLAM_CPP_USE_ASSEMBLE=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- exact evolve/model improvements relative to the update-cell continuation baseline:
  - 10m: `1.266910 s -> 1.074628 s`
  - 2h: `9.865382 s -> 8.403064 s`
  - 40h: `177.525983 s -> 142.210454 s`
- all three compare windows passed exact compare

### Next

- keep `Assemble_Flux_2` as an accepted exact kernel on this line
- continue with the next native gaps in this order:
  1. nodechain state commit / final apply
  2. deeper `Caculate_Roe_Flux_2` ownership if it still ranks above the remaining river-step kernels
  3. `Caculate_Roe_matrix`

## 2026-03-16 C++ fullchain pushdown Roe-matrix step

### Done

- implemented an exact native `Caculate_Roe_matrix` kernel behind:
  - `ISLAM_CPP_USE_ROE_MATRIX=1`
- moved the full interface loop for:
  - `Lambda1/Lambda2`
  - LeVeque correction masks
  - `alpha1/alpha2`
  - `Vactor1/Vactor2/Vactor1_T/Vactor2_T`
  - interface regime counters
  into C++
- extended the branch-local benchmark tool so it can explicitly toggle:
  - `ISLAM_CPP_USE_ASSEMBLE`
  - `ISLAM_CPP_USE_ROE_MATRIX`
- validated the candidate on:
  - 10m
  - 2h
  - 40h

### Findings

- this kernel is a much cleaner native target than nodechain commit because it is mostly arrays-only work with stable dtype semantics
- the key exactness rule here was to preserve the NumPy path's `float32` intermediate arithmetic, then write the resulting values into the existing `float64` eigenvector arrays
- once `Roe_matrix` is native, the remaining river-step bottleneck picture changes again:
  - `Caculate_Roe_Flux_2` is now the dominant river-step hotspot
  - `Caculate_face_U_C` becomes the next clean arrays-heavy candidate
  - nodechain remains the biggest non-river-step domain

### Results

- accepted continuation exact config is now:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - `ISLAM_CPP_USE_ASSEMBLE=1`
  - `ISLAM_CPP_USE_ROE_MATRIX=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- exact evolve/model improvements relative to the assemble continuation baseline:
  - 10m: `1.074628 s -> 0.997237 s`
  - 2h: `8.403064 s -> 7.561386 s`
  - 40h: `142.210454 s -> 124.534376 s`
- all three compare windows passed exact compare

### Next

- keep `Caculate_Roe_matrix` as an accepted exact kernel on this line
- continue with the next native gaps in this order:
  1. nodechain state commit / final apply
  2. deeper `Caculate_Roe_Flux_2`
  3. `Caculate_face_U_C`

## 2026-03-16 C++ fullchain pushdown Face_U_C step

### Done

- implemented an exact native `Caculate_face_U_C` kernel behind:
  - `ISLAM_CPP_USE_FACE_UC=1`
- moved the whole interface loop for:
  - `sqrt(max(S, limit))`
  - weighted `F_U`
  - pressure-ratio / average `F_C`
  - one-side-dry / both-dry branches
  into:
  - `cpp/river_kernels.hpp`
  - `cpp/river_kernels.cpp`
  - `cython_river_kernels.pyx`
  - `river_for_net.py`
- updated `tools/profile_cpp_exact_serial.py` so this kernel can be benchmarked and compared independently
- validated the candidate on:
  - 10m
  - 2h
  - 40h

### Findings

- this kernel only became exact after preserving the Python path's mixed dtype behavior:
  - `cell_limits` must stay `float64`
  - `sqrt_left/right`, `fu`, `fc` must be evaluated in `double`
  - write-back to `F_U/F_C` happens as `float32`
- with that rule in place, the whole `face_uc` interface loop becomes a low-risk nativeization target and no longer needs Python per-face dispatch

### Results

- current accepted continuation exact config:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=1`
  - `ISLAM_CPP_USE_ASSEMBLE=1`
  - `ISLAM_CPP_USE_ROE_MATRIX=1`
  - `ISLAM_CPP_USE_FACE_UC=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- exact evolve/model improvements relative to the Roe-matrix continuation baseline:
  - 10m: `0.997237 s -> 0.927344 s`
  - 2h: `7.561386 s -> 7.022465 s`
  - 40h: `124.534376 s -> 115.940719 s`
- all three compare windows passed exact compare

### Next

- keep `Caculate_face_U_C` as an accepted exact kernel on this line
- continue with the next real gaps in this order:
  1. nodechain state commit / final apply native 化
  2. deeper `Caculate_Roe_Flux_2` ownership if it still dominates after commit pushdown
  3. only then revisit a fuller native full-step loop

## 2026-03-16 C++ fullchain pushdown nodechain prebound-fast step

### Done

- implemented a deeper exact nodechain fast path behind:
  - `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- prebound the left/right stage-boundary direct-fast context on each river:
  - table refs
  - indices
  - guard thresholds
  - swap-sign flags
- replaced the old per-call direct-fast shell with a side-code based prebound helper in the nodechain loop
- moved commit/write-back in this path to side-specific exact helpers, avoiding:
  - layout dict construction
  - side string conversion
  - dynamic boundary-face `setattr` choreography
- validated the candidate on:
  - 10m
  - 2h
  - 40h

### Findings

- this keeps the same exact numeric closure kernel, but removes a meaningful amount of Python-side wrapper cost around it
- the gain lands exactly where expected:
  - `nodechain.apply_and_boundary_closure`
  - `nodechain.final_apply`
  - `boundary_updater.total`
- 40h `nodechain.prebound_fast_hits = 4010220`, so this path is not theoretical; it is the actual hot path

### Results

- current accepted continuation exact config:
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
- exact evolve/model improvements relative to the Face_U_C continuation baseline:
  - 10m: `0.927344 s -> 0.860548 s`
  - 2h: `7.022465 s -> 6.488843 s`
  - 40h: `115.940719 s -> 109.425894 s`
- all three compare windows passed exact compare

### Next

- keep this nodechain prebound-fast path as an accepted exact component on this line
- continue with the next real gaps in this order:
  1. deeper `Caculate_Roe_Flux_2` ownership / C++ exact pushdown
  2. nodechain residual/Ac 主体进一步 native 化
  3. only then revisit a fuller native full-step loop

## 2026-03-15 Phase 0-2

### Done

- preserved the current FAST experimental line before opening the Cython branch
- recorded preflight git status and diff artifacts on the FAST worktree
- created preservation branch:
  - `backup/pre-cython-branch-20260315-224054`
- created untracked artifact snapshot:
  - `/tmp/pre_cython_branch_20260315-224054_untracked_snapshot.tar.gz`
- created clean isolated worktree:
  - `/tmp/feature_cython_exact_nodechain_top3`
- created branch:
  - `feature/cython-exact-nodechain-top3`
- confirmed this branch starts from clean accepted baseline `dea3202`
- wrote branch layout report
- mapped the serial internal-node iteration chain and documented:
  - call chain
  - math/state semantics
  - data layout / Python object costs
  - exact Cythonization plan

### Findings

- the serial internal-node solve is orchestrated from `Rivernet.Update_internal_boundary_conditions`
- the accepted baseline already hits `_stage_boundary_fix_level_cython_fast` for the low-level exact stage-boundary closure path when flags allow it
- the remaining serial nodechain cost is therefore likely dominated by:
  - network-level node/branch traversal
  - Python dict / tuple / string overhead
  - repeated method dispatch
- this supports the planned exact Cython strategy:
  - integerize and compile the nodechain shell first
  - then profile serial `Evolve` and Cythonize the remaining Top 3 outer loops

### Next

- Phase 3: establish single-process Python baseline
- run serial-only profiling on 10-minute and long case
- generate hotspot Top 3 report
- then implement `cython_node_iteration.pyx`

## 2026-03-15 Phase 3

### Done

- added evolve-only benchmark/profiling infrastructure:
  - `tools/run_serial_case.py`
  - `tools/summarize_cprofile.py`
  - `tools/profile_islam_evolve_only.py`
- refactored `Islam.py` so benchmark tooling can import and run:
  - `build_net(...)`
  - `maybe_run_warmup(...)`
  - `prepare_net_for_evolve(...)`
  - `run_prepared_evolve(...)`
  - `run_main_case(...)`
  - `main()`
- copied missing `bound/` input files into the new worktree so the clean branch is runnable
- ran evolve-only serial baseline for:
  - 10-minute case
  - 2-hour representative long case
- generated serial baseline and hotspot reports

### Findings

- once initialization is excluded, the hotspot picture is clean and stable
- confirmed Top 3 on the single-process exact line:
  1. internal node iteration chain
  2. `Caculate_Roe_Flux_2`
  3. `Update_cell_proprity2`
- `Assemble_Flux_2` is important but ranks behind `Update_cell_proprity2`
- nodechain remains the dominant exact serial cost by a wide margin

### Next

- Phase 4: implement `cython_node_iteration.pyx`
- keep exact semantics and single-process execution
- then reprofile and move to the remaining Top 3 kernels

## 2026-03-16 Phase 4-5

### Done

- implemented exact single-process nodechain kernel:
  - `cython_node_iteration.pyx`
- added exact build entry for branch-local kernels:
  - `build_cython_exact_kernels.py`
- wired nodechain runtime flag:
  - `ISLAM_USE_CYTHON_NODECHAIN`
- implemented river-side Cython kernels in:
  - `cython_river_kernels.pyx`
- wired exact Roe-flux batch flag:
  - `ISLAM_USE_CYTHON_ROE_FLUX`
- wired exact update-cell flag:
  - `ISLAM_USE_CYTHON_UPDATE_CELL`
- confirmed the accepted exact candidate on short and medium cases is:
  - `nodechain + Roe flux`
- documented implementation split and local-kernel before/after numbers

### Findings

- nodechain Cython path is exact on 10-minute and 2-hour cases
- nodechain standalone gain is modest:
  - about `1.03x`
- Roe-flux Cython path is the dominant serial win once the real hit-path is active
- best current exact candidate is:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- this candidate is exact on:
  - 10-minute case
  - 2-hour case
- `Update_cell_proprity2` Cython kernel is fast but still drifts, so it remains feature-flagged and excluded from the exact candidate

### Next

- finish the 40-hour no-profile single-process exact candidate run for:
  - `nodechain + Roe flux`
- compare it against:
  - `result/serial_python_40h_noprof`
- then write:
  - `cython_error_report.md`
  - `cython_speed_report.md`
  - `final_benchmark_matrix.md`
  - `final_cython_branch_recommendation.md`
  - `overnight_hand_off.md`

## 2026-03-16 Phase 6-7

### Done

- completed the 40-hour no-profile exact-candidate run:
  - `reports/cython_nodechain_roe_40h_exact_summary.json`
- completed strict 40-hour compare:
  - `reports/cython_nodechain_roe_40h_exact_compare.json`
- completed a 2-hour profiled run for the accepted exact candidate:
  - `reports/cython_nodechain_roe_2h_profile_hit_v3_summary.json`
  - `reports/cython_nodechain_roe_2h_profile_hit_v3_profile_summary.json`
- updated the validation, speed, benchmark-matrix, recommendation, and hand-off reports

### Findings

- accepted exact candidate on this branch:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- 40-hour evolve/model time:
  - `562.262618 s -> 213.933772 s`
  - speedup `2.628x`
- 40-hour evolve wall:
  - `565.037927 s -> 217.559511 s`
  - speedup `2.597x`
- 40-hour step count is unchanged:
  - `29783 -> 29783`
- strict compare remains clean:
  - `allclose = true`
- update-cell kernel still drifts and remains excluded from the exact candidate

### Next

- clean up and stage the accepted exact-Cython work for a checkpoint commit
- keep generated build artifacts and failed experimental paths out of the final commit

## 2026-03-16 fullchain pushdown phase 0 reset

### Done

- kept the source worktree `/home/xin/River_net_parallel` untouched as the protected dirty experiment source
- created a clean continuation branch:
  - `feature/cpp-exact-evolve-fullchain-pushdown-next`
- created a clean continuation worktree:
  - `/tmp/feature_cpp_exact_evolve_fullchain_pushdown_next`
- recorded source-state reports for the continuation line:
  - `cpp_fullchain_preflight_git_status.txt`
  - `cpp_fullchain_untracked_inventory.md`
  - `cpp_fullchain_branch_layout.md`

### Findings

- the accepted exact baseline we continue from is `1d71dee`
- the source worktree still contains the rejected-but-useful `Assemble_Flux_2` native prototype and benchmark artifacts, so leaving it untouched is the safest way to preserve that work
- the new continuation line can now profile and push kernels down without mixing those rejected changes into accepted code

### Next

- re-profile the accepted exact configuration in this clean continuation branch
- write the remaining native-gap and hotspot reports against the real accepted path
- then push the next exact C++ kernel after accepted update-cell, not the rejected assemble experiment
## 2026-03-16 Stage 1-2: flux-residual-fullstep branch bootstrap and Roe flux deep ownership

- Created clean worktree/branch:
  - `feature/cpp-exact-evolve-flux-residual-fullstep`
  - `/tmp/feature_cpp_exact_evolve_flux_residual_fullstep`
- Rebuilt missing Cython extensions in the new worktree so the accepted exact baseline was actually comparable.
- Recorded new branch preflight:
  - `reports/cpp_pushdown_preflight_git_status.txt`
  - `reports/cpp_pushdown_untracked_inventory.md`
  - `reports/cpp_pushdown_branch_layout.md`
- Wrote remaining-gap reports for the accepted exact path:
  - `reports/evolve_remaining_python_chain_after_faceuc.md`
  - `reports/evolve_remaining_hotspots_after_faceuc_top10.md`
  - `reports/evolve_native_gap_ranked_after_faceuc.md`
- Implemented deeper exact general-HR Roe flux ownership:
  - prebound native interface plan
  - deep C++ per-face loop
  - feature flag `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- Validation:
  - 10m strict compare: pass
  - 2h strict compare: pass
  - 40h strict compare: pass
- Headline `evolve/model time`:
  - 10m `0.860548 -> 0.843206 s`
  - 2h `6.488843 -> 6.374767 s`
  - 40h `109.425894 -> 106.473473 s`
- Result:
  - accepted checkpoint candidate
  - next biggest remaining resistance is nodechain, not bridge shape

## 2026-03-16 Stage 0-1: nodechain-deepnative branch bootstrap and nodechain native-gap audit

### Done

- Created clean continuation branch/worktree from accepted flux-deep exact baseline:
  - `feature/cpp-exact-evolve-nodechain-deepnative`
  - `/tmp/feature_cpp_exact_evolve_nodechain_deepnative`
- Rebuilt the Cython extensions in the new worktree so profiling and compare could run from a clean branch-local state.
- Recorded branch-local preflight files:
  - `reports/cpp_nodechain_push_preflight_git_status.txt`
  - `reports/cpp_nodechain_push_untracked_inventory.md`
  - `reports/cpp_nodechain_push_branch_layout.md`
- Ran an accepted-config 2h single-process exact profile in the new worktree and wrote:
  - `reports/cpp_nodechainpush_accepted_2h_summary.json`
  - `reports/cpp_nodechainpush_accepted_2h_perf.json`
- Wrote nodechain-specific native-gap reports:
  - `reports/nodechain_remaining_python_chain_after_fluxdeep.md`
  - `reports/nodechain_native_gap_ranked_after_fluxdeep.md`
  - `reports/nodechain_hotspots_breakdown_after_fluxdeep.md`

### Findings

- The remaining nodechain gap is no longer in the closure formula itself; it is in ownership around the formula.
- The dominant remaining nodechain sub-cost is still:
  - `apply_and_boundary_closure`
- The accepted prebound fast path is active, but each closure still pays for:
  - a Python river helper call
  - Python-owned commit / `_refresh_cell_state`
  - Python-owned boundary-face attribute writeback
- Residual / `Ac` still re-read boundary-face state and width data through Python-owned lookups.
- This explains why the accepted exact path is still above `100 s` on 40h even after flux deep ownership succeeded.

### Next

- push `apply_and_boundary_closure` deeper so native code owns:
  - branch plan
  - closure context
  - per-iteration face-state cache
  - immediate post-closure state refresh / commit
- then move residual / `Ac` to consume that native-owned face state instead of Python attrs and repeated lookups

## 2026-03-16 Stage 2: nodechain apply/closure deep ownership

### Done

- added a deeper exact nodechain apply path behind:
  - `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- exported `compute_stage_boundary_mainline_fast(...)` into the nodechain Cython layer
- added `NodeBoundaryDeepPlan` plus:
  - precompiled side/layout indices
  - prebound table refs
  - typed state-array views
  - face-state cache
  - implicit-vector write-back support
- routed node iteration apply/final apply through the deep plan when enabled
- replaced repeated Python-owned boundary closure and width lookup traffic with native-owned closure + face cache reuse
- validated the accepted candidate on:
  - 10m
  - 2h
  - 40h

### Findings

- this step is a real ownership pushdown, not another wrapper tweak
- 40h exact compare passes:
  - `allclose = true`
- headline evolve/model improved:
  - `106.473473 s -> 92.091939 s`
- the first milestone is now met:
  - `40h < 100 s`
- 40h nodechain sub-costs dropped materially:
  - `nodechain.total`: `65.117052 s -> 36.756061 s`
  - `apply_and_boundary_closure`: `25.879760 s -> 14.925780 s`
  - `residual_and_ac`: `1.742821 s -> 0.213633 s`
  - `final_apply`: `4.360243 s -> 2.637463 s`
- Python boundary ownership in the hot path is effectively gone:
  - `cython_to_python_boundary_calls`: `4010220 -> 0`
  - `cython_to_python_width_calls`: `3414560 -> 0`

### Next

- checkpoint this path as the new accepted exact candidate for the continuation line
- continue from the new `~92.09 s` baseline and focus on:
  - residual / Ac / Jacobian / stopping deeper native ownership
  - final apply / state commit deeper native ownership
  - only after that, fullstep native loop
