# Overnight Progress Log

## F0

- Exported current FAST dirty state to:
  - `reports/fast_preflight_git_status.txt`
  - `reports/fast_preflight_worktree.diff`
  - `reports/fast_preflight_index.diff`
- Created safety checkpoints:
  - branch `safety_fast_20260315_194332`
  - worktree `/tmp/fast_mode_safety_20260315_194332`
- Wrote `reports/fast_preflight.md`
- Continue: yes

## F1

- Confirmed `fast-mode-30s` remains the primary FAST worktree.
- Wrote `reports/fast_branch_layout.md`.
- Validation policy changed:
  - default exact only needs smoke-level protection
  - main effort now targets FAST 40h wall-clock reduction
- Continue: yes

## F2

- Mirrored the exact-side 40-hour dt profile into the FAST worktree:
  - `reports/dt_profile_exact_40h.md`
  - `reports/dt_limiter_topk_exact_40h.csv`
- Ported the default-off dt-profile infrastructure into the FAST line so current FAST candidates can emit `dt_profile.csv` without affecting normal runs.
- Re-profiled the current best FAST candidate (`adaptive_cfl125`) on the full 40-hour case:
  - `reports/dt_profile_fast_40h.md`
  - `reports/dt_limiter_topk_fast_40h.csv`
- Key findings:
  - exact: `29969` steps
  - current best FAST: `23895` steps
  - step reduction is only about `1.25x`
  - current best FAST is still overwhelmingly limited by one internal-node-adjacent branch end:
    - `river8 / cell15 / n11`
  - limiter category share is still effectively `100% internal_node`
- Conclusion:
  - the main 30-second gap is still a **total-step-count** problem
- the current FAST improvements help, but they do not yet change the long-run limiter structure enough
- Continue: yes

## F3

- Added `tools/fast_sweep.py` to automate 40-hour FAST candidate runs and evaluate them against the accepted exact baseline.
- The sweep now records, for each candidate:
  - wall time
  - model/evolve time
  - total steps
  - mean dt
  - NSE delta
  - control-point max abs / peak error / arrival-time error
  - volume error
- Generated the first sweep reports:
  - `reports/fast_sweep_matrix.md`
  - `reports/fast_sweep_top_candidates.md`
- First generated batch result:
  - best so far: `response_root_iter2_cfl175_dt125_fixed`
  - wall: `127.369616 s`
  - model/evolve: `123.9998128414154 s`
  - steps: `16939`
  - max abs overall: `0.03392045196741478`
- Main takeaway from the first batch:
  - the current Pareto front clearly prefers **fixed** aggressive FAST over the present adaptive gate
  - the meaningful gain is again coming from **step-count reduction**, not from preserving adaptive selectivity
- Continue: yes

## Stage 1 Carry-In

- Branch: `fast-mode-30s`
- Base commit: `dea3202`
- FAST infrastructure restored from isolated snapshot commit `4cf4721` without bringing back failed exact-only experiments.
- Verified default exact path on the FAST line remains isolated from FAST behavior:
  - 10-minute exact rerun still matches the accepted exact 10-minute baseline with `allclose=true`.
- Continue: yes

## Stage 6 Setup

- Added adaptive FAST gating on top of the existing `FAST_MODE` infrastructure instead of widening the default exact path.
- Wired river-side dt limiter metadata into the network object so FAST can react to the actual global dt limiter source.
- Added adaptive enable/disable policy based on:
  - limiter category
  - repeated limiter streak on the same internal node
  - previous node-level change
  - previous residual magnitude
  - near-dry guard
- Added run-summary export of adaptive activation counts and decision reasons.
- Added a 10-minute adaptive smoke result:
  - output: `result/overnight_fast_adaptive_10m`
  - default exact on the FAST line remains strict-equal
  - adaptive 10-minute control-point error remained in the `1e-4` range
- Continue: yes

## Stage 6 Results

- Ran 40-hour adaptive FAST full case without extra CFL scaling:
  - output: `result/exp_fastmode_adaptive_py311_40h`
  - wall: `242.30 s`
  - model/evolve: `235.27873492240906 s`
  - steps: `29989`
  - adaptive enabled steps: `29987 / 29989`
  - result: too slow, and control-point `Q` max abs remained above `1e-2`
- Ran 40-hour adaptive FAST with CFL acceleration:
  - output: `result/exp_fastmode_adaptive_cfl125_py311_40h`
  - wall: `193.09 s`
  - model/evolve: `186.73348426818848 s`
  - steps: `23895`
  - adaptive enabled steps: `23893 / 23895`
  - result: better than the previous FAST baseline `fast_40h_iter5_cfl125` on both speed and error, but still not close to `30 s`
- Key finding:
  - dt/step count remains the dominant barrier
  - the current adaptive gate is functionally "always on" after the first two steps, so it does not materially change the long-run limiter structure
- Continue: yes

## F4

- Reframed the overnight goal around FAST-only wall-clock reduction rather than exact-side cleanup.
- Preserved default exact behavior and only added new controls behind FAST mode:
  - `ISLAM_FAST_NODE_REFRESH_EVERY`
  - `ISLAM_FAST_NODE_REFRESH_MODE=hold|predict`
  - `ISLAM_FAST_NODE_REFRESH_WARMUP_STEPS`
- Implemented periodic internal-node refresh in both serial and process FAST paths:
  - full fast internal-node solve only on refresh steps
  - intermediate steps reapply cached node levels (`hold`) or extrapolated levels (`predict`)
- Added refresh counters to `run_summary.json`.
- Continue: yes

## F5

- Built out the FAST sweep to cover structural refresh candidates and regenerate the matrix from previously saved JSON reports without rerunning everything.
- Main structural findings:
  - `predict` refresh is too unstable for long 40-hour runs and can produce catastrophic control-point errors.
  - `hold` refresh is much more robust.
  - increasing refresh interval reduces wall-clock mostly by cutting boundary-updater cost; step count changes much less.
- New representative FAST frontier:
  - `response_root_iter2_cfl20_dt135_fixed_refresh2hold`
    - wall `92.689026 s`
    - model `89.52261996269226 s`
    - steps `14756`
    - max_abs `0.06244182586669922`
  - `response_root_iter2_cfl20_dt135_fixed_refresh3hold`
    - wall `87.270943 s`
    - model `83.9566490650177 s`
    - steps `14758`
    - max_abs `0.07947444915771484`
  - `response_root_iter2_cfl225_dt15_fixed_refresh3hold`
    - wall `78.14009 s`
    - model `74.83811044692993 s`
    - steps `13062`
    - max_abs `0.12782573699951172`
  - `response_root_iter2_cfl30_dt20_fixed_refresh3hold`
    - wall `59.379443 s`
    - model `56.126713275909424 s`
    - steps `9836`
    - max_abs `0.5854339599609375`
- Best balance so far:
  - `response_root_iter2_cfl20_dt135_fixed_refresh3hold`
- Fastest so far:
  - `response_root_iter2_cfl30_dt20_fixed_refresh3hold`
- Continue: yes

## F6

- Re-profiled the current speed-optimal candidate with dt-profile enabled:
  - output: `result/exp_fastmode_speedopt_dtprofile_py311_40h`
  - report: `reports/dt_profile_fast_40h.md`
  - top-k CSV: `reports/dt_limiter_topk_fast_40h.csv`
- Updated fast-side dt picture:
  - current speed-optimal FAST still has limiter category share `100% internal_node`
  - total steps reduced to `9836`
  - mean dt increased to `14.64 s`
  - top limiter concentrated at `river1 / cell15 / n8`
- Conclusion:
  - the overnight FAST work did reduce total steps materially
  - but even the fastest current path still needs either fewer steps or cheaper per-step cost to reach `30 s`
- Continue: yes

## F7

- Re-ran a minimal 10-minute exact smoke on the FAST worktree:
  - output: `result/tmp_exact_smoke_after_fast_10m`
  - result: completes successfully with `181` steps and no FAST dependency
- Updated canonical FAST reports:
  - `reports/fast_eval_vs_accepted40h.md`
  - `reports/fast_eval_speed_opt_vs_accepted40h.md`
  - `reports/fast_sweep_matrix.md`
  - `reports/fast_sweep_top_candidates.md`
- Next: finalize recommendation and handoff docs, then create a FAST checkpoint if git metadata writes succeed.
- Continue: yes
