# Overnight Progress Log

## Stage 0

- Recorded current git status and exported worktree/index diffs.
- Verified `main` is clean at `dea3202`.
- Documented the preserved dirty experimental delta from `fast_mode_snapshot_20260314`.
- Created recovery checkpoints:
  - `safety_main_20260314_223414`
  - `fast_mode_snapshot_20260314`
  - `/tmp/fastmode_backup`
- Continue: yes

## Stage 1

- Created isolated exact work line:
  - branch `exact-baseline-clean`
  - worktree `/tmp/overnight_exact_baseline_clean`
- Created isolated FAST work line:
  - branch `fast-mode-30s`
  - worktree `/tmp/overnight_fast_mode_30s`
- Wrote branch layout and carry-in / exclusion policy to keep exact and FAST lines separated.
- Found that `git worktree` does not materialize untracked Islam runtime inputs under `bound/`.
- Attached read-only symlinks for:
  - `bound/`
  - `cython_cross_section.cpython-311-x86_64-linux-gnu.so`
- Verified both worktrees can run the default exact path with a 10-minute smoke:
  - exact line: `181` steps, model time `2.62 s`
  - FAST line baseline: `181` steps, model time `2.55 s`
- Continue: yes

## Stage 2

- Added safe benchmark infrastructure:
  - `tools/overnight_benchmark.py`
  - env-gated `ISLAM_SAVE_RUN_SUMMARY=1`
  - network-level `run_summary.json` export in `Rivernet.py`
- Fixed report-root isolation so benchmark reports stay in the exact worktree, not `main`.
- Ran fresh exact benchmarks from the clean exact line:
  - `exact_10m`: strict compare passed, `allclose=true`
  - `exact_40h`: strict compare passed, `allclose=true`
- Re-evaluated current FAST 40h artifacts against the fresh exact-40h reference:
  - `fast_40h_iter5_cfl125`
  - `fast_40h_iter5_nocfl`
- Wrote unified matrix:
  - `reports/benchmark_matrix.md`
- Key finding:
  - current clean exact rerun is still slower than the accepted 40h reference, so no exact performance commit is acceptable yet
  - current FAST artifacts are faster than the clean exact rerun, but still far from `30 s` and still exceed the desired max-abs threshold on `Q`
- Continue: yes

## Stage 3

- Added default-off dt / limiter profiling infrastructure:
  - `ISLAM_SAVE_DT_PROFILE=1`
  - river-side limiter capture in `Caculate_CFL_time_for_river_net()`
  - network-side step profile export to `dt_profile.csv`
  - offline report generator `tools/dt_profile_report.py`
- Verified 10-minute exact dt-profile smoke remains strict-equal after fixing the `dt_min -> Python float` precision regression.
- Ran 40h exact dt-profile:
  - output: `result/overnight_exact_dtprofile_40h`
  - strict compare: passed
  - report: `reports/dt_profile_exact_40h.md`
  - top-k: `reports/dt_limiter_topk_exact_40h.csv`
- Ran 40h FAST dt-profile on the preserved FAST snapshot worktree:
  - output: `/tmp/overnight_fast_snapshot/handoff_network_model_20260312/result/overnight_fast_dtprofile_40h`
  - report mirrored into exact-line reports as `reports/dt_profile_fast_40h.md`
  - top-k: `reports/dt_limiter_topk_fast_40h.csv`
- Key finding:
  - exact and FAST are both overwhelmingly limited by a single internal-node-adjacent branch end
  - exact: `river1 / cell15 / node n8`
  - FAST: `river8 / cell15 / node n11`
  - exact steps: `29969`
  - FAST steps: `23754`
  - exact model time per step: `0.00871 s`
  - FAST model time per step: `0.00722 s`
  - this points more strongly to total step count as the dominant barrier to a `30 s` target than to per-step Python overhead alone
- Continue: yes

## Stage 4

- Added `tools/hotpath_diff_vs_dea3202.py` to compare the current exact line against a clean `dea3202` reference worktree on the same 10-minute case.
- Used wrapper-based timing on the default exact parallel path to measure `boundary_updater`.
- Used a serial isolation run to measure per-call costs of:
  - `Caculate_face_U_C`
  - `Caculate_Roe_matrix`
  - `Caculate_Roe_Flux_2`
  - `Assemble_Flux_2`
  - `Update_cell_proprity2`
- Wrote the result to `reports/hotpath_diff_vs_dea3202.md`.
- Key findings:
  - current exact vs raw `dea3202` is effectively flat within timing noise on the target hot functions
  - `boundary_updater` is not slower than `dea3202`
  - `parallel_river_pool.py` is unchanged relative to `dea3202`
  - no diff hunk lands inside the listed hot river kernels or the default parallel boundary-updater path
- Conclusion:
  - there is no evidence that the current default exact path is carrying residual experimental overhead in the stage-4 target functions
  - the remaining exact work should move to new local-kernel optimization, not cleanup of prior node-solve experiments
- Continue: yes

## Stage 5

- Tried an exact-only local-kernel cleanup focused on the river body hot path:
  - precomputed per-cell `s_limit` / `bed_level` caches
  - one-shot `QIN` zeroing in `Update_cell_proprity2()`
  - a few section-name/table lookups replaced with prebound refs in hot loops
- Protected the failed experiment as `reports/stage5_failed_local_kernel_experiment.diff` before reverting it from the default exact path.
- Exact validation:
  - 10-minute exact strict compare: passed
  - 40h exact strict compare: passed
- Measured 40h exact result for the experiment:
  - wall: `262.34158 s`
  - model/evolve: `254.96488738059998 s`
  - step_count: `29969`
- Compared with the previous clean exact rerun in `reports/benchmark_matrix.md`:
  - wall improved from `268.230295 s` to `262.34158 s`
  - model/evolve improved from `260.7422785758972 s` to `254.96488738059998 s`
- But the experiment still does not satisfy exact acceptance:
  - it remains far slower than the accepted exact baseline (`147.10 s` wall / `139.86 s` evolve)
  - therefore it cannot be committed as a default exact change
- Local-kernel before/after profiling was saved to:
  - `reports/local_kernel_profile_before_after.md`
  - `reports/local_kernel_profile_before_after.json`
- Conclusion:
  - exact local cleanup produced only a modest gain versus the clean rerun and does not close the gap to the accepted exact baseline
  - the code experiment was reverted from the default exact path; only the reports/tooling remain
- Continue: yes

## Stage 6

- Restored the isolated FAST infrastructure onto `fast-mode-30s` without reintroducing failed exact-only experiments.
- Re-verified that the FAST line does not pollute the default exact path:
  - `fast_line_exact_10m_check`: strict compare passed again, `allclose=true`
- Added an adaptive FAST gate driven by the current global dt limiter source and recent node history.
- Ran 40-hour adaptive FAST without extra CFL scaling:
  - wall: `242.30 s`
  - model/evolve: `235.27873492240906 s`
  - steps: `29989`
  - enabled steps: `29987 / 29989`
  - result: too slow, and control-point `Q` max abs stayed above `1e-2`
- Ran 40-hour adaptive FAST with `ISLAM_FAST_CFL_SCALE=1.25` and `ISLAM_FAST_DT_INCREASE_FACTOR=1.1`:
  - wall: `193.09 s`
  - model/evolve: `186.73348426818848 s`
  - steps: `23895`
  - enabled steps: `23893 / 23895`
  - relative to the previous FAST best (`fast_40h_iter5_cfl125`), both speed and error improved slightly
- Updated benchmark matrix with:
  - `fast_40h_adaptive`
  - `fast_40h_adaptive_cfl125`
- Continue: yes

## Stage 7

- Final overnight conclusion:
  - the `30 s` target is still dominated primarily by total step count / dt-limiter structure, not by fast-path admission or small orchestration fixes
  - the current adaptive FAST gate mostly behaves like "always on after warm-up", so it does not materially change the long-run limiter landscape
  - exact-only local-kernel cleanup did not recover enough ground to challenge the accepted exact baseline
- Produced handoff reports:
  - `reports/final_overnight_recommendation.md`
  - `reports/overnight_hand_off.md`
- Continue: no
