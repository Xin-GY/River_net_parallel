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
