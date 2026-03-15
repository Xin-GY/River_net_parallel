# Overnight Progress Log

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
